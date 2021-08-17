from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns
from . import views


# This is example of download deck url: /anki/cards.apkg/?lesson=rotating-planet&deck=devman_lessons
urlpatterns = [
    path('anki/cards/', views.download_deck),
    path('anki/feedback/', views.show_feedback_form, name='anki_feedback'),
]
urlpatterns = format_suffix_patterns(urlpatterns, allowed=['apkg'])
