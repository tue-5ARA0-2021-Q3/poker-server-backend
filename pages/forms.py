from django import forms

class SearchGameForm(forms.Form):
    game_or_coordinator_id = forms.UUIDField()