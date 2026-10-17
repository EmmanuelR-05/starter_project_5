from django.contrib import admin

from .models import FoundWord, Game, LeaderBoard, LeaderBoardEntry, Player, ValidWord

for model in (Game, Player, LeaderBoard, LeaderBoardEntry, ValidWord, FoundWord):
    admin.site.register(model)
