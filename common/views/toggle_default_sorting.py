from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponseBadRequest
from django.http import HttpResponseRedirect

from common.utils.secure_url import secure_url

data = {
    'Task': "task_step_date_sorting",
    'Deal': "deal_step_date_sorting",
}


def toggle_default_sorting(request: WSGIRequest) -> HttpResponseRedirect:
    model = request.GET.get('model')

    if model:
        key = data.get(model)
        if key is None:
            return HttpResponseBadRequest('Unknown model.')
        if key in request.session:
            del request.session[key]
        else:
            request.session[key] = True

    next_url = request.GET.get('next_url')
    if not next_url:
        return HttpResponseBadRequest('The "next_url" parameter is required.')
    query_dict = request.GET.copy()
    query_dict.pop('model', None)
    query_dict.pop('next_url', None)
    if query_dict:
        sml = '&' if '?' in next_url else '?'
        next_url += f'{sml}{query_dict.urlencode()}'
               
    return HttpResponseRedirect(secure_url(next_url, request))
