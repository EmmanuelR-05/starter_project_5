from django.urls import path

from .views import (
    CreateGameBySizeView,
    DictionaryLanguagesView,
    DeleteGameView,
    DeleteLeaderBoardEntryView,
    GameDetailView,
    GameLeaderBoardView,
    GameListView,
    GameWordsView,
    JoinGameView,
    LeaderBoardEntryDetailView,
    LoginView,
    LogoutView,
    PlayerSessionFinishView,
    PlayerSessionStartView,
    PlayerSessionWordsView,
    RegisterView,
)

urlpatterns = [
    path("dictionaries/", DictionaryLanguagesView.as_view(), name="dictionary-languages"),
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/token/", LoginView.as_view(), name="auth-token"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),

    # Create a random game of a given size       GET /api/game/4/
    path("game/<int:size>/", CreateGameBySizeView.as_view(), name="create-game-by-size"),

    # All games                                  GET /api/games/
    path("games/", GameListView.as_view(), name="game-list"),

    # One game (GET) / rename it (PATCH)         /api/games/<uuid>/
    path("games/<uuid:id>/", GameDetailView.as_view(), name="game-detail"),

    # Delete a game                              DELETE /api/games/<uuid>/delete/
    path("games/<uuid:id>/delete/", DeleteGameView.as_view(), name="game-delete"),

    # Extras
    path("games/<uuid:id>/join/", JoinGameView.as_view(), name="game-join"),
    path("games/<uuid:id>/words/", GameWordsView.as_view(), name="game-words"),
    path("sessions/<int:player_id>/start/", PlayerSessionStartView.as_view(),
         name="session-start"),
    path("sessions/<int:player_id>/words/", PlayerSessionWordsView.as_view(),
         name="session-words"),
    path("sessions/<int:player_id>/finish/", PlayerSessionFinishView.as_view(),
         name="session-finish"),

    # Leaderboard for a game (GET) / add entry (POST)
    path("games/<uuid:id>/leaderboard/", GameLeaderBoardView.as_view(), name="game-leaderboard"),

    # One leaderboard entry                      GET /api/leaderboard/<uuid>/
    path("leaderboard/<uuid:id>/", LeaderBoardEntryDetailView.as_view(), name="entry-detail"),

    # Delete a leaderboard entry                 DELETE /api/leaderboard/<uuid>/delete/
    path("leaderboard/<uuid:id>/delete/", DeleteLeaderBoardEntryView.as_view(), name="entry-delete"),
]
