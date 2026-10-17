from __future__ import annotations

from django.contrib.staticfiles import finders
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .boggle_solver import Boggle
from .models import Game, LeaderBoard, LeaderBoardEntry, Player, ValidWord
from .randomGen import random_grid
from .readJSONFile import read_json_to_list
from .serializers import (
    GameSerializer,
    LeaderBoardEntrySerializer,
    LeaderBoardSerializer,
)

# Put the dictionary in boggle_backend/static/data/ and make sure one of
# these names matches the real file name.
DICTIONARY_FILES = ["data/full-wordlist.json", "data/full-words.json"]
_dictionary_cache = None


def load_dictionary():
    """Load the word list once and reuse it for every request."""
    global _dictionary_cache
    if _dictionary_cache is None:
        for name in DICTIONARY_FILES:
            path = finders.find(name)
            if path:
                _dictionary_cache = read_json_to_list(path)
                break
        else:
            raise FileNotFoundError(
                "Dictionary file not found in static/data/ "
                f"(looked for: {', '.join(DICTIONARY_FILES)})"
            )
    return _dictionary_cache


def get_or_create_leaderboard(game):
    leaderboard, _ = LeaderBoard.objects.get_or_create(
        game=game, defaults={"title": f"Leaderboard for {game.name}"}
    )
    return leaderboard


class CreateGameBySizeView(APIView):
    """GET /api/game/<size>/  -> creates, stores and returns a random Game."""
    permission_classes = [AllowAny]

    def get(self, request, size: int):
        if size < 3 or size > 10:
            return Response({"detail": "size must be between 3 and 10."},
                            status=status.HTTP_400_BAD_REQUEST)

        dictionary_language = request.query_params.get("dictionary", "English")

        try:
            with transaction.atomic():
                grid = random_grid(size)
                now = timezone.now()
                name = f"Random{size}Grid:{now.strftime('%Y-%m-%d %H:%M:%S')}"

                solver = Boggle(grid, load_dictionary())
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
    permission_classes = [AllowAny]

    def post(self, request, id):
        game = get_object_or_404(Game, id=id)
        if not request.user.is_authenticated:
            return Response({"detail": "Authentication required"},
                            status=status.HTTP_401_UNAUTHORIZED)
        Player.objects.get_or_create(game=game, user=request.user)
        return Response({"message": "joined game"})


class GameLeaderBoardView(APIView):
    """
    GET  /api/games/<uuid>/leaderboard/  -> leaderboard with its entries
    POST /api/games/<uuid>/leaderboard/  -> add an entry
         {"player_name": "Sam", "words_found_count": 12, "total_time_seconds": 95}
    """
    permission_classes = [AllowAny]

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

        user = request.user if request.user.is_authenticated else None
        player_name = str(request.data.get("player_name", "Anonymous")).strip() or "Anonymous"

        entry = LeaderBoardEntry.objects.create(
            leaderboard=leaderboard,
            user=user,
            player_name=player_name[:100],
            words_found_count=words_found_count,
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
    """GET /api/games/<uuid>/words/  -> every valid word with its points"""
    permission_classes = [AllowAny]

    def get(self, request, id):
        game = get_object_or_404(Game, id=id)
        words = ValidWord.objects.filter(game=game)
        return Response([{"word": w.word, "points": w.points} for w in words])


class DeleteGameView(APIView):
    """DELETE /api/games/<uuid>/delete/  (also removes its leaderboard + entries)"""
    permission_classes = [AllowAny]

    def delete(self, request, id):
        game = get_object_or_404(Game, id=id)
        game.delete()
        return Response({"message": "game deleted"})


class DeleteLeaderBoardEntryView(APIView):
    """DELETE /api/leaderboard/<uuid>/delete/"""
    permission_classes = [AllowAny]

    def delete(self, request, id):
        entry = get_object_or_404(LeaderBoardEntry, id=id)
        entry.delete()
        return Response({"message": "leaderboard entry deleted"})
