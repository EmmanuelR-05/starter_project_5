from __future__ import annotations

from django.contrib.staticfiles import finders
from django.db import IntegrityError, transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.views import APIView

from .boggle_solver import Boggle
from .models import FoundWord, Game, LeaderBoard, LeaderBoardEntry, Player, ValidWord
from .randomGen import random_grid
from .readJSONFile import read_json_to_list
from .serializers import (
    GameSerializer,
    LeaderBoardEntrySerializer,
    LeaderBoardSerializer,
    PlayerSessionSerializer,
    RegistrationSerializer,
    UserSerializer,
)

# Put the dictionary in boggle_backend/static/data/ and make sure one of
# these names matches the real file name.
DICTIONARY_FILES = {
    "English": ["data/full-wordlist.json", "data/full-words.json"],
    "French": ["data/french-wordlist.json"],
}
DICTIONARY_ALIASES = {
    "en": "English",
    "english": "English",
    "fr": "French",
    "french": "French",
}
_dictionary_cache = {}


def normalize_dictionary_language(language):
    """Resolve a language name or ISO code to its canonical display name."""
    canonical = DICTIONARY_ALIASES.get(str(language).strip().casefold())
    if canonical is None:
        supported = ", ".join(DICTIONARY_FILES)
        raise ValueError(f"Unsupported dictionary language. Choose one of: {supported}.")
    return canonical


def load_dictionary(language="English"):
    """Load and cache the selected word list."""
    canonical = normalize_dictionary_language(language)
    if canonical not in _dictionary_cache:
        for name in DICTIONARY_FILES[canonical]:
            path = finders.find(name)
            if path:
                _dictionary_cache[canonical] = read_json_to_list(path)
                break
        else:
            raise FileNotFoundError(
                f"Dictionary file for {canonical} was not found in static/data/ "
                f"(looked for: {', '.join(DICTIONARY_FILES[canonical])})"
            )
    return _dictionary_cache[canonical]


def get_or_create_leaderboard(game):
    leaderboard, _ = LeaderBoard.objects.get_or_create(
        game=game, defaults={"title": f"Leaderboard for {game.name}"}
    )
    return leaderboard


class DictionaryLanguagesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            [
                {"code": code, "name": name}
                for code, name in (("en", "English"), ("fr", "French"))
            ]
        )


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {"token": token.key, "user": UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class LoginView(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        user = Token.objects.select_related("user").get(key=response.data["token"]).user
        return Response({"token": response.data["token"], "user": UserSerializer(user).data})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.user.auth_token.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CreateGameBySizeView(APIView):
    """Create a stored random game; GET is retained for the original API client."""
    permission_classes = [IsAuthenticated]

    def get(self, request, size: int):
        return self.create_game(request, size)

    def post(self, request, size: int):
        return self.create_game(request, size)

    def create_game(self, request, size: int):
        if size < 3 or size > 10:
            return Response({"detail": "size must be between 3 and 10."},
                            status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        provided_name = request.data.get("name", request.query_params.get("name"))
        if provided_name is None:
            name = f"Random{size}Grid:{now.strftime('%Y-%m-%d %H:%M:%S')}"
        else:
            name = str(provided_name).strip()
            if not name or len(name) > 200:
                return Response(
                    {"detail": "name must contain 1 to 200 characters."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        requested_language = request.query_params.get(
            "dictionary",
            request.data.get(
                "dictionary",
                request.data.get(
                    "dictionary_language",
                    request.data.get("language", request.query_params.get("language", "English")),
                ),
            ),
        )
        try:
            dictionary_language = normalize_dictionary_language(requested_language)
        except ValueError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            dictionary = load_dictionary(dictionary_language)
        except FileNotFoundError as error:
            return Response({"detail": str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            with transaction.atomic():
                grid = random_grid(size)

                solver = Boggle(grid, dictionary)
                found_words = solver.getSolution()
                normalized = sorted({
                    str(w).strip().upper() for w in found_words if str(w).strip()
                })

                creator = request.user if request.user.is_authenticated else None
                game = Game.objects.create(
                    name=name,
                    size=size,
                    grid=grid,
                    dictionary_language=dictionary_language,
                    solution_words=normalized,
                    created_by=creator,
                )
                if creator:
                    Player.objects.get_or_create(game=game, user=creator)

                LeaderBoard.objects.create(game=game, title=f"Leaderboard for {game.name}")

                ValidWord.objects.bulk_create(
                    [ValidWord(game=game, word=w, points=len(w)) for w in normalized]
                )

            return Response(GameSerializer(game).data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"detail": f"Game creation failed: {e}"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GameListView(APIView):
    """GET /api/games/  -> all games, newest first."""
    permission_classes = [AllowAny]

    def get(self, request):
        games = Game.objects.all().order_by("-date_created")
        return Response(GameSerializer(games, many=True).data)


class GameDetailView(APIView):
    """
    GET   /api/games/<uuid>/  -> one game
    PATCH /api/games/<uuid>/  -> rename it: {"name": "My new name"}
    """
    permission_classes = [AllowAny]

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request, id):
        game = get_object_or_404(Game, id=id)
        return Response(GameSerializer(game).data)

    def patch(self, request, id):
        game = get_object_or_404(Game, id=id)
        name = str(request.data.get("name", "")).strip()
        if not name or len(name) > 200:
            return Response({"detail": "name is required (max 200 characters)."},
                            status=status.HTTP_400_BAD_REQUEST)
        game.name = name
        game.save(update_fields=["name"])
        return Response(GameSerializer(game).data)


class JoinGameView(APIView):
    """POST /api/games/<uuid>/join/  (login required)"""
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        game = get_object_or_404(Game, id=id)
        player, created = Player.objects.get_or_create(
            game=game, user=request.user, completed=False
        )
        return Response(
            PlayerSessionSerializer(player).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class PlayerSessionStartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, player_id):
        player = get_object_or_404(Player, id=player_id, user=request.user)
        if player.completed:
            return Response(
                {"detail": "This game session is already complete."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if player.started_at is None:
            player.started_at = timezone.now()
            player.save(update_fields=["started_at"])
        return Response(PlayerSessionSerializer(player).data)


class PlayerSessionWordsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, player_id):
        player = get_object_or_404(
            Player.objects.select_related("game", "user"),
            id=player_id,
            user=request.user,
        )
        if player.started_at is None:
            return Response(
                {"detail": "Start the game session before submitting words."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if player.completed:
            return Response(
                {"detail": "This game session is already complete."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        word = str(request.data.get("word", "")).strip().upper()
        if word not in {item.upper() for item in player.game.solution_words}:
            return Response({"detail": "Word is not a solution for this game."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                FoundWord.objects.create(player=player, word=word, points=1)
                Player.objects.filter(id=player.id).update(score=F("score") + 1)
        except IntegrityError:
            return Response({"detail": "Word has already been submitted."},
                            status=status.HTTP_409_CONFLICT)

        player.refresh_from_db()
        return Response(
            {
                "word": word,
                "points": 1,
                "score": player.score,
                "words_found_count": player.found_words.count(),
                "words_remaining_count": max(
                    0,
                    len(player.game.solution_words) - player.found_words.count(),
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class PlayerSessionFinishView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, player_id):
        with transaction.atomic():
            player = get_object_or_404(
                Player.objects.select_for_update().select_related("game", "user"),
                id=player_id,
                user=request.user,
            )
            if player.started_at is None:
                return Response(
                    {"detail": "Start the game session before completing it."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if player.completed:
                return Response(
                    {"detail": "This game session is already complete."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            completed_at = timezone.now()
            elapsed_seconds = max(
                0, int((completed_at - player.started_at).total_seconds())
            )
            words_found_count = player.found_words.count()
            words_not_found_count = max(
                0, len(player.game.solution_words) - words_found_count
            )
            player.completed = True
            player.completed_at = completed_at
            player.save(update_fields=["completed", "completed_at"])

            leaderboard = get_or_create_leaderboard(player.game)
            entry = LeaderBoardEntry.objects.create(
                leaderboard=leaderboard,
                user=player.user,
                player_name=player.user.get_username()[:100],
                words_found_count=words_found_count,
                words_not_found_count=words_not_found_count,
                total_time_seconds=elapsed_seconds,
                score=player.score,
            )

        return Response(
            {
                "session": PlayerSessionSerializer(player).data,
                "leaderboard_entry": LeaderBoardEntrySerializer(entry).data,
            },
            status=status.HTTP_201_CREATED,
        )


class GameLeaderBoardView(APIView):
    """
    GET  /api/games/<uuid>/leaderboard/  -> leaderboard with its entries
    POST /api/games/<uuid>/leaderboard/  -> add an entry
         {"player_name": "Sam", "words_found_count": 12, "total_time_seconds": 95}
    """
    permission_classes = [AllowAny]

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request, id):
        game = get_object_or_404(Game, id=id)
        return Response(LeaderBoardSerializer(get_or_create_leaderboard(game)).data)

    def post(self, request, id):
        game = get_object_or_404(Game, id=id)
        leaderboard = get_or_create_leaderboard(game)

        try:
            words_found_count = int(request.data.get("words_found_count", 0))
            total_time_seconds = int(request.data.get("total_time_seconds", 0))
        except (TypeError, ValueError):
            return Response(
                {"detail": "words_found_count and total_time_seconds must be integers."},
                status=status.HTTP_400_BAD_REQUEST)
        if words_found_count < 0 or total_time_seconds < 0:
            return Response({"detail": "Values cannot be negative."},
                            status=status.HTTP_400_BAD_REQUEST)
        if words_found_count > len(game.solution_words):
            return Response(
                {"detail": "words_found_count cannot exceed the game's solution count."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user if request.user.is_authenticated else None
        player_name = str(request.data.get("player_name", "Anonymous")).strip() or "Anonymous"

        entry = LeaderBoardEntry.objects.create(
            leaderboard=leaderboard,
            user=user,
            player_name=player_name[:100],
            words_found_count=words_found_count,
            words_not_found_count=len(game.solution_words) - words_found_count,
            total_time_seconds=total_time_seconds,
            score=words_found_count,   # simple scoring rule: 1 point per word
        )
        return Response(LeaderBoardEntrySerializer(entry).data,
                        status=status.HTTP_201_CREATED)


class LeaderBoardEntryDetailView(APIView):
    """GET /api/leaderboard/<uuid>/  -> one leaderboard entry"""
    permission_classes = [AllowAny]

    def get(self, request, id):
        entry = get_object_or_404(LeaderBoardEntry, id=id)
        return Response(LeaderBoardEntrySerializer(entry).data)


class GameWordsView(APIView):
    """GET /api/games/<uuid>/words/  -> every valid word, for administrators only."""
    permission_classes = [IsAdminUser]

    def get(self, request, id):
        game = get_object_or_404(Game, id=id)
        words = ValidWord.objects.filter(game=game)
        return Response([{"word": w.word, "points": w.points} for w in words])


class DeleteGameView(APIView):
    """DELETE /api/games/<uuid>/delete/  (also removes its leaderboard + entries)"""
    permission_classes = [IsAuthenticated]

    def delete(self, request, id):
        game = get_object_or_404(Game, id=id)
        game.delete()
        return Response({"message": "game deleted"})


class DeleteLeaderBoardEntryView(APIView):
    """DELETE /api/leaderboard/<uuid>/delete/"""
    permission_classes = [IsAuthenticated]

    def delete(self, request, id):
        entry = get_object_or_404(LeaderBoardEntry, id=id)
        entry.delete()
        return Response({"message": "leaderboard entry deleted"})
