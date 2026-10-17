import uuid

from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models


class Game(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    size = models.PositiveIntegerField(validators=[MinValueValidator(3)])
    grid = models.JSONField()
    dictionary_language = models.CharField(max_length=25, default="English")
    solution_words = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE,
                                   related_name="games_created", null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Name: {self.name} Size: {self.size}"


class Player(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="players")
    score = models.IntegerField(default=0)
    completed = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)


class LeaderBoard(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    game = models.OneToOneField(Game, on_delete=models.CASCADE, related_name="leaderboard")
    title = models.CharField(max_length=200, blank=True, default="")

    def __str__(self):
        return self.title or f"Leaderboard for {self.game.name}"


class LeaderBoardEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    leaderboard = models.ForeignKey(LeaderBoard, on_delete=models.CASCADE, related_name="entries")
    user = models.ForeignKey(User, on_delete=models.SET_NULL,
                             related_name="boogle_leaderboard_entries", null=True, blank=True)
    player_name = models.CharField(max_length=100, default="Anonymous")
    words_found_count = models.PositiveIntegerField(default=0)
    total_time_seconds = models.PositiveIntegerField(default=0)
    score = models.IntegerField(default=0)
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Most words first, then fastest time
        ordering = ["-words_found_count", "total_time_seconds"]


class ValidWord(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="valid_words")
    word = models.CharField(max_length=50)
    points = models.IntegerField()


class FoundWord(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    word = models.CharField(max_length=50)
    points = models.IntegerField()
