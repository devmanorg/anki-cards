from django.urls import path
from . import views


# This is example of download deck url: /anki/cards.apkg/?lesson=rotating-planet&deck=devman_lessons
urlpatterns = [
    path('anki/cards.apkg', views.download_deck, name='download_anki_deck'),
    path('anki/feedback/', views.show_feedback_form, name='anki_feedback'),
]
