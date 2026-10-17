from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Game, LeaderBoard, LeaderBoardEntry

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email")
        read_only_fields = ("id", "username", "email")


class LeaderBoardEntrySerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = LeaderBoardEntry
        fields = (
            "id", "leaderboard", "user", "player_name",
            "words_found_count", "total_time_seconds", "score", "saved_at",
        )
        read_only_fields = ("id", "leaderboard", "saved_at")


class LeaderBoardSerializer(serializers.ModelSerializer):
    entries = LeaderBoardEntrySerializer(many=True, read_only=True)

    class Meta:
        model = LeaderBoard
        fields = ("id", "game", "title", "entries")
        read_only_fields = ("id",)


class GameSerializer(serializers.ModelSerializer):
    leaderboard = LeaderBoardSerializer(read_only=True)

    class Meta:
        model = Game
        fields = (
            "id", "name", "size", "grid", "dictionary_language",
            "solution_words", "date_created", "leaderboard",
        )
        read_only_fields = fields
