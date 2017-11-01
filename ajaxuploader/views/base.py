try:
    import json
except ImportError:
    from django.utils import simplejson as json

from django.core.files.base import File
from django.core.serializers.json import DjangoJSONEncoder

from django.http import HttpResponse, HttpResponseBadRequest, Http404, HttpResponseNotAllowed

from ajaxuploader.backends.local import LocalUploadBackend
from ajaxuploader.signals import file_uploaded


class AjaxFileUploader(object):
    def __init__(self, backend=None, **kwargs):
        if backend is None:
            backend = LocalUploadBackend
        self.get_backend = lambda: backend(**kwargs)

    def __call__(self, request, *args, **kwargs):
        return self._ajax_upload(request, *args, **kwargs)

    def _ajax_upload(self, request, *args, **kwargs):
        if request.method == "POST":
            if request.is_ajax():
                is_raw = False
                try:
                    filename = request.POST['qqfilename']
                    # FILES is a dictionary in Django but Ajax Upload gives
                    # the uploaded file an ID based on a random number, so it
                    # cannot be guessed here in the code. Rather than editing
                    # Ajax Upload to pass the ID in the querystring, observe
                    # that each upload is a separate request, so FILES should
                    # only have one entry. Thus, we can just grab the first
                    # (and only) value in the dict.
                    upload = request.FILES.values()[0]
                except (KeyError, IndexError):
                    return HttpResponseBadRequest("AJAX request not valid")
            else:
                raise Http404("Bad Upload")

            backend = self.get_backend()

            # custom filename handler
            filename = (backend.update_filename(request, filename, *args, **kwargs) \
                        or filename)
            # save the file
            backend.setup(filename, *args, **kwargs)
            success = backend.upload(upload, filename, is_raw, *args, **kwargs)

            if success:
                file_uploaded.send(sender=self.__class__, backend=backend, request=request)

            # callback
            extra_context = backend.upload_complete(request, filename, *args, **kwargs)

            # let Ajax Upload know whether we saved it or not
            ret_json = {'success': success, 'filename': filename}
            if extra_context is not None:
                ret_json.update(extra_context)

            # although "application/json" is the correct content type, IE throws a fit
            return HttpResponse(json.dumps(ret_json, cls=DjangoJSONEncoder), content_type='text/html; charset=utf-8')
        else:
            response = HttpResponseNotAllowed(['POST'])
            response.write("ERROR: Only POST allowed")
            return response
