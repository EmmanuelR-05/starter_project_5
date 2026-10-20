# Backend additions (guest play + remaining words)

Your API requires login for session endpoints and hides the solution list, so guests
can't validate words or see missed words. Add two read-only endpoints.

## api/views.py (append)
```python
class CheckWordView(APIView):
    """POST /api/games/<uuid>/check/  {"word": "CAT"} -> {"valid": true}"""
    permission_classes = [AllowAny]

    def post(self, request, id):
        game = get_object_or_404(Game, id=id)
        word = str(request.data.get("word", "")).strip().upper()
        return Response({"word": word, "valid": word in {w.upper() for w in game.solution_words}})


class RevealWordsView(APIView):
    """POST /api/games/<uuid>/reveal/  {"found": ["CAT"]} -> {"remaining": [...]} (call after Stop)"""
    permission_classes = [AllowAny]

    def post(self, request, id):
        game = get_object_or_404(Game, id=id)
        found = {str(w).upper() for w in request.data.get("found", [])}
        return Response({"remaining": [w for w in game.solution_words if w.upper() not in found]})
```

## api/urls.py
Add `CheckWordView, RevealWordsView` to the import list, then inside `urlpatterns`:
```python
path("games/<uuid:id>/check/", CheckWordView.as_view(), name="game-check"),
path("games/<uuid:id>/reveal/", RevealWordsView.as_view(), name="game-reveal"),
```

## Optional: CORS (only if you don't use the Vite proxy)
In `boggle_backend/settings.py`: `CORS_ALLOW_ALL_ORIGINS = True` (dev only).
