import tempfile
from urllib.parse import quote
from more_itertools import flatten

from django.shortcuts import get_list_or_404, render
from django.http import HttpResponse
from django.http import Http404
from django.views.decorators.http import require_http_methods
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt

from rest_framework import serializers

from .models import BaseCard, Deck, Issue
from .export.apkg import export_cards


def download_deck(request):
    cards_query = BaseCard.objects.select_related('basiccard', 'englishcard', 'deck').filter(published=True)

    # Перемешиваем подряд идущие карты на случай, если все они по одному и тому же улучшению код-ревью.
    cards_query = cards_query.order_by('?')

    requested_decks_slugs = {slug.strip() for slug in request.GET.getlist('deck')}
    requested_decks = get_list_or_404(Deck, slug__in=requested_decks_slugs)

    found_decks_slugs = {deck.slug for deck in requested_decks}
    if found_decks_slugs < requested_decks_slugs:
        raise Http404(f'Decks not found: {requested_decks_slugs - found_decks_slugs}')

    exported_decks = flatten([deck.get_descendants(include_self=True) for deck in requested_decks])
    exported_decks = set(exported_decks)  # ORM objects will be compared by id

    cards_query = cards_query.filter(deck__in=exported_decks)
    lessons_slugs = request.GET.getlist('lesson')
    if lessons_slugs:
        cards_query = cards_query.filter(lesson__slug__in=lessons_slugs)
    enhancements_slugs = request.GET.getlist('enhancement')
    if enhancements_slugs:
        cards_query = cards_query.filter(enhancement__slug__in=enhancements_slugs)

    output_file_name = request.GET.get('name', 'devman_decks.apkg')

    with tempfile.NamedTemporaryFile(suffix='.apkg') as apkg_file:
        export_cards(apkg_file.name, cards_query)

        apkg_file.flush()

        # FIXME How large apkg file can be? Should Nginx handle file disribution?
        response = HttpResponse(apkg_file.read(), content_type='application/force-download')
        response['Content-Disposition'] = f'attachment; filename="{quote(output_file_name)}"'
        return response


class IssueSerializer(serializers.ModelSerializer):

    class Meta:
        model = Issue
        fields = ['card', 'description']
        extra_kwargs = {
            'description': {
                'allow_blank': False,
                'required': True,
                'max_length': 200,
            }
        }


# HTML page can be embeded into anki cards app, so iframe support is enabled
@xframe_options_exempt
@csrf_exempt
@require_http_methods(["GET", "POST"])
def show_feedback_form(request):
    errors = None
    if request.method == 'POST':
        serializer = IssueSerializer(data=request.POST)

        if serializer.is_valid():
            Issue.objects.get_or_create(  # simple protection from duplicated issues
                card=serializer.validated_data['card'],
                description=serializer.validated_data['description'],
                defaults={
                    'author': request.user.is_authenticated and request.user or None,
                }
            )

            return render(request, 'anki/success_feedback_form.html', {})

        else:
            errors = serializer.errors

    return render(request, 'anki/feedback_form.html', {
        'errors': errors,
    })
