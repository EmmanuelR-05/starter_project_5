from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Game, LeaderBoard, LeaderBoardEntry, Player

User = get_user_model()


class RegistrationSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(
        write_only=True, min_length=8, trim_whitespace=False
    )

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


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
            "words_found_count", "words_not_found_count",
            "total_time_seconds", "score", "saved_at",
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
            "date_created", "leaderboard",
        )
        read_only_fields = fields


class PlayerSessionSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    words_found_count = serializers.SerializerMethodField()
    words_remaining_count = serializers.SerializerMethodField()

    class Meta:
        model = Player
        fields = (
            "id", "game", "user", "score", "words_found_count", "words_remaining_count",
            "completed", "joined_at", "started_at", "completed_at",
        )
        read_only_fields = fields

    def get_words_found_count(self, obj):
        return obj.found_words.count()

    def get_words_remaining_count(self, obj):
        return max(
            0,
            len(obj.game.solution_words) - self.get_words_found_count(obj),
        )
