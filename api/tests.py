from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import FoundWord, Game, LeaderBoard, LeaderBoardEntry, Player
from .serializers import RegistrationSerializer
from .views import _dictionary_cache, load_dictionary

User = get_user_model()


class RegistrationSerializerTests(APITestCase):
    def test_password_is_hashed_when_user_is_created(self):
        serializer = RegistrationSerializer(
            data={"username": "alice", "email": "alice@example.com", "password": "safe-pass-123"}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()

        self.assertTrue(user.check_password("safe-pass-123"))
        self.assertNotEqual(user.password, "safe-pass-123")


class AuthenticationApiTests(APITestCase):
    def test_registration_returns_a_token_and_user(self):
        response = self.client.post(
            reverse("auth-register"),
            {"username": "alice", "email": "alice@example.com", "password": "safe-pass-123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"]["username"], "alice")
        self.assertTrue(Token.objects.filter(key=response.data["token"]).exists())

    def test_registration_rejects_duplicate_usernames(self):
        User.objects.create_user(username="alice", password="safe-pass-123")

        response = self.client.post(
            reverse("auth-register"),
            {"username": "alice", "password": "another-safe-pass"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.filter(username="alice").count(), 1)

    def test_registration_rejects_weak_passwords(self):
        response = self.client.post(
            reverse("auth-register"),
            {"username": "alice", "password": "password"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(username="alice").exists())

    def test_login_returns_token_and_logout_revokes_it(self):
        user = User.objects.create_user(username="alice", password="safe-pass-123")
        login = self.client.post(
            reverse("auth-token"),
            {"username": "alice", "password": "safe-pass-123"},
            format="json",
        )

        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertEqual(login.data["user"]["username"], "alice")
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {login.data['token']}")
        logout = self.client.post(reverse("auth-logout"), format="json")

        self.assertEqual(logout.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Token.objects.filter(user=user).exists())

    def test_reads_are_public_but_game_creation_requires_a_token(self):
        response = self.client.get(reverse("game-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        with patch("api.views.random_grid", return_value=[["A"] * 3 for _ in range(3)]), \
                patch("api.views.load_dictionary", return_value=["AAA"]):
            create_response = self.client.get(reverse("create-game-by-size", args=[3]))

        self.assertEqual(create_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(Game.objects.count(), 0)

    def test_authenticated_game_creation_initializes_leaderboard(self):
        user = User.objects.create_user(username="alice", password="safe-pass-123")
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        with patch("api.views.random_grid", return_value=[["A"] * 3 for _ in range(3)]), \
                patch("api.views.load_dictionary", return_value=["AAA"]):
            response = self.client.get(reverse("create-game-by-size", args=[3]))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        game = Game.objects.get()
        self.assertEqual(game.created_by, user)
        self.assertTrue(LeaderBoard.objects.filter(game=game).exists())

    def test_game_update_and_leaderboard_submission_require_authentication(self):
        game = Game.objects.create(
            name="Game",
            size=3,
            grid=[["A"] * 3 for _ in range(3)],
            solution_words=["CAT", "DOG"],
        )
        leaderboard = LeaderBoard.objects.create(game=game)

        update = self.client.patch(
            reverse("game-detail", args=[game.id]), {"name": "Updated"}, format="json"
        )
        submit = self.client.post(
            reverse("game-leaderboard", args=[game.id]),
            {"player_name": "Guest", "words_found_count": 2, "total_time_seconds": 10},
            format="json",
        )

        self.assertEqual(update.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(submit.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(leaderboard.entries.count(), 0)

    def test_reads_are_public_and_all_other_game_writes_require_authentication(self):
        game = Game.objects.create(
            name="Game",
            size=3,
            grid=[["A"] * 3 for _ in range(3)],
            solution_words=["CAT", "DOG"],
        )
        leaderboard = LeaderBoard.objects.create(game=game)
        entry = LeaderBoardEntry.objects.create(
            leaderboard=leaderboard, player_name="Guest"
        )

        public_reads = [
            self.client.get(reverse("game-detail", args=[game.id])),
            self.client.get(reverse("game-leaderboard", args=[game.id])),
            self.client.get(reverse("entry-detail", args=[entry.id])),
        ]
        protected_writes = [
            self.client.post(reverse("game-join", args=[game.id]), format="json"),
            self.client.delete(reverse("game-delete", args=[game.id])),
            self.client.delete(reverse("entry-delete", args=[entry.id])),
        ]

        self.assertTrue(all(response.status_code == status.HTTP_200_OK for response in public_reads))
        self.assertTrue(
            all(response.status_code == status.HTTP_401_UNAUTHORIZED for response in protected_writes)
        )
        self.assertTrue(Game.objects.filter(id=game.id).exists())
        self.assertTrue(LeaderBoardEntry.objects.filter(id=entry.id).exists())

    def test_authenticated_leaderboard_submission_is_associated_with_user(self):
        user = User.objects.create_user(username="alice", password="safe-pass-123")
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        game = Game.objects.create(
            name="Game",
            size=3,
            grid=[["A"] * 3 for _ in range(3)],
            solution_words=["CAT", "DOG"],
        )

        response = self.client.post(
            reverse("game-leaderboard", args=[game.id]),
            {"player_name": "Alice", "words_found_count": 2, "total_time_seconds": 10},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        entry = LeaderBoardEntry.objects.get()
        self.assertEqual(entry.user, user)
        self.assertEqual(response.data["score"], 2)
        self.assertEqual(response.data["words_not_found_count"], 0)


class MultiplayerSessionApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="safe-pass-123")
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        self.game = Game.objects.create(
            name="Game",
            size=3,
            grid=[["A"] * 3 for _ in range(3)],
            solution_words=["CAT", "DOG"],
        )

    def test_session_join_start_submit_and_finish_flow(self):
        join = self.client.post(reverse("game-join", args=[self.game.id]), format="json")
        self.assertEqual(join.status_code, status.HTTP_201_CREATED)
        player_id = join.data["id"]
        self.assertFalse(join.data["completed"])

        repeated_join = self.client.post(
            reverse("game-join", args=[self.game.id]), format="json"
        )
        self.assertEqual(repeated_join.status_code, status.HTTP_200_OK)
        self.assertEqual(repeated_join.data["id"], player_id)

        start = self.client.post(reverse("session-start", args=[player_id]), format="json")
        self.assertEqual(start.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(start.data["started_at"])

        valid_word = self.client.post(
            reverse("session-words", args=[player_id]), {"word": " cat "}, format="json"
        )
        duplicate_word = self.client.post(
            reverse("session-words", args=[player_id]), {"word": "CAT"}, format="json"
        )
        invalid_word = self.client.post(
            reverse("session-words", args=[player_id]), {"word": "NOPE"}, format="json"
        )
        self.assertEqual(valid_word.status_code, status.HTTP_201_CREATED)
        self.assertEqual(valid_word.data, {
            "word": "CAT",
            "points": 1,
            "score": 1,
            "words_found_count": 1,
            "words_remaining_count": 1,
        })
        self.assertEqual(duplicate_word.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(invalid_word.status_code, status.HTTP_400_BAD_REQUEST)

        finish = self.client.post(
            reverse("session-finish", args=[player_id]), format="json"
        )
        self.assertEqual(finish.status_code, status.HTTP_201_CREATED)
        self.assertTrue(finish.data["session"]["completed"])
        self.assertEqual(finish.data["leaderboard_entry"]["words_found_count"], 1)
        self.assertEqual(finish.data["leaderboard_entry"]["words_not_found_count"], 1)
        self.assertEqual(finish.data["session"]["words_remaining_count"], 1)
        self.assertEqual(finish.data["leaderboard_entry"]["score"], 1)
        self.assertEqual(finish.data["leaderboard_entry"]["user"]["username"], "alice")
        self.assertEqual(FoundWord.objects.filter(player_id=player_id).count(), 1)
        self.assertEqual(Player.objects.get(id=player_id).score, 1)

        after_finish = self.client.post(
            reverse("session-words", args=[player_id]), {"word": "DOG"}, format="json"
        )
        self.assertEqual(after_finish.status_code, status.HTTP_400_BAD_REQUEST)

    def test_session_words_require_started_session_and_owner(self):
        join = self.client.post(reverse("game-join", args=[self.game.id]), format="json")
        player_id = join.data["id"]
        not_started = self.client.post(
            reverse("session-words", args=[player_id]), {"word": "CAT"}, format="json"
        )
        self.assertEqual(not_started.status_code, status.HTTP_400_BAD_REQUEST)

        other_user = User.objects.create_user(username="bob", password="another-safe-pass")
        other_token = Token.objects.create(user=other_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {other_token.key}")
        not_owner = self.client.post(
            reverse("session-start", args=[player_id]), format="json"
        )
        self.assertEqual(not_owner.status_code, status.HTTP_404_NOT_FOUND)

    def test_completed_game_can_be_replayed_as_a_new_session(self):
        first = self.client.post(reverse("game-join", args=[self.game.id]), format="json")
        self.client.post(reverse("session-start", args=[first.data["id"]]), format="json")
        self.client.post(reverse("session-finish", args=[first.data["id"]]), format="json")

        replay = self.client.post(reverse("game-join", args=[self.game.id]), format="json")

        self.assertEqual(replay.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(replay.data["id"], first.data["id"])
        self.assertEqual(Player.objects.filter(game=self.game, user=self.user).count(), 2)


class DictionaryLanguageApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="safe-pass-123")
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def tearDown(self):
        _dictionary_cache.clear()

    def test_french_word_list_is_loaded_and_normalized_for_ascii_tiles(self):
        words = load_dictionary("fr")

        self.assertIn("bonjour", words)
        self.assertIn("maison", words)
        self.assertIn("ecole", words)
        self.assertIn("coeur", words)
        self.assertNotIn("cœur", words)
        self.assertGreater(len(words), 100_000)

    def test_language_list_is_public(self):
        self.client.credentials()

        response = self.client.get(reverse("dictionary-languages"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [
            {"code": "en", "name": "English"},
            {"code": "fr", "name": "French"},
        ])

    def test_french_game_creation_uses_selected_dictionary(self):
        grid = [
            ["C", "H", "A"],
            ["X", "T", "X"],
            ["X", "X", "X"],
        ]
        with patch("api.views.random_grid", return_value=grid), \
                patch("api.views.load_dictionary", return_value=["CHAT"]) as load_words:
            response = self.client.get(
                reverse("create-game-by-size", args=[3]), {"language": "fr"}
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        load_words.assert_called_once_with("French")
        game = Game.objects.get()
        self.assertEqual(game.dictionary_language, "French")
        self.assertIn("CHAT", game.solution_words)
        self.assertNotIn("solution_words", response.data)

    def test_french_game_creation_solves_with_bundled_dictionary(self):
        grid = [
            ["B", "O", "N"],
            ["X", "X", "X"],
            ["X", "X", "X"],
        ]
        _dictionary_cache.clear()
        with patch("api.views.random_grid", return_value=grid):
            response = self.client.get(
                reverse("create-game-by-size", args=[3]), {"dictionary": "French"}
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("solution_words", response.data)
        self.assertIn("BON", Game.objects.get().solution_words)

    def test_unsupported_language_is_rejected_without_creating_game(self):
        response = self.client.get(
            reverse("create-game-by-size", args=[3]), {"dictionary": "Klingon"}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Game.objects.count(), 0)


class GameCrudApiTests(APITestCase):
    def setUp(self):
        user = User.objects.create_user(username="alice", password="safe-pass-123")
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_game_create_list_retrieve_update_and_delete(self):
        grid = [["A", "A", "A"] for _ in range(3)]
        with patch("api.views.random_grid", return_value=grid), \
                patch("api.views.load_dictionary", return_value=["AAA"]):
            created = self.client.post(
                reverse("create-game-by-size", args=[3]),
                {"name": "Assignment Game", "dictionary_language": "English"},
                format="json",
            )

        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.data["name"], "Assignment Game")
        self.assertNotIn("solution_words", created.data)
        game_id = created.data["id"]
        self.assertEqual(Game.objects.get(id=game_id).solution_words, ["AAA"])
        self.assertEqual(LeaderBoard.objects.filter(game_id=game_id).count(), 1)

        game_list = self.client.get(reverse("game-list"))
        game_detail = self.client.get(reverse("game-detail", args=[game_id]))
        self.assertEqual(game_list.status_code, status.HTTP_200_OK)
        self.assertEqual(game_list.data[0]["id"], game_id)
        self.assertEqual(game_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(game_detail.data["name"], "Assignment Game")

        updated = self.client.patch(
            reverse("game-detail", args=[game_id]), {"name": "Renamed Game"}, format="json"
        )
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.data["name"], "Renamed Game")

        deleted = self.client.delete(reverse("game-delete", args=[game_id]))
        self.assertEqual(deleted.status_code, status.HTTP_200_OK)
        self.assertFalse(Game.objects.filter(id=game_id).exists())
        self.assertFalse(LeaderBoard.objects.filter(game_id=game_id).exists())

    def test_leaderboard_entry_can_be_retrieved_and_deleted(self):
        game = Game.objects.create(
            name="Game", size=3, grid=[["A"] * 3 for _ in range(3)]
        )
        leaderboard = LeaderBoard.objects.create(game=game)
        entry = LeaderBoardEntry.objects.create(
            leaderboard=leaderboard,
            player_name="Alice",
            words_found_count=5,
            total_time_seconds=42,
            score=5,
        )

        retrieved = self.client.get(reverse("entry-detail", args=[entry.id]))
        deleted = self.client.delete(reverse("entry-delete", args=[entry.id]))

        self.assertEqual(retrieved.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieved.data["words_found_count"], 5)
        self.assertEqual(retrieved.data["words_not_found_count"], 0)
        self.assertEqual(deleted.status_code, status.HTTP_200_OK)
        self.assertFalse(LeaderBoardEntry.objects.filter(id=entry.id).exists())

    def test_solution_words_are_hidden_and_solution_list_requires_admin(self):
        game = Game.objects.create(
            name="Game",
            size=3,
            grid=[["A"] * 3 for _ in range(3)],
            solution_words=["CAT", "DOG"],
        )
        self.client.credentials()

        game_list = self.client.get(reverse("game-list"))
        game_detail = self.client.get(reverse("game-detail", args=[game.id]))
        solution_list = self.client.get(reverse("game-words", args=[game.id]))

        self.assertEqual(game_list.status_code, status.HTTP_200_OK)
        self.assertEqual(game_detail.status_code, status.HTTP_200_OK)
        self.assertNotIn("solution_words", game_list.data[0])
        self.assertNotIn("solution_words", game_detail.data)
        self.assertEqual(solution_list.status_code, status.HTTP_401_UNAUTHORIZED)

        regular_user = User.objects.create_user(username="bob", password="another-safe-pass")
        regular_token = Token.objects.create(user=regular_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {regular_token.key}")
        self.assertEqual(
            self.client.get(reverse("game-words", args=[game.id])).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_leaderboard_submission_computes_words_not_found(self):
        game = Game.objects.create(
            name="Game",
            size=3,
            grid=[["A"] * 3 for _ in range(3)],
            solution_words=["CAT", "DOG", "BIRD"],
        )

        response = self.client.post(
            reverse("game-leaderboard", args=[game.id]),
            {"player_name": "Alice", "words_found_count": 2, "total_time_seconds": 10},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["words_not_found_count"], 1)
