"""URL configuration."""
from django.urls import path
from views.render import render_preview
from api.import_data import import_objects
from api.upload import upload_xml
from api.users import update_user

urlpatterns = [
    path("render/", render_preview),
    path("api/import/", import_objects),
    path("api/upload/", upload_xml),
    path("api/users/<int:user_id>/", update_user),
]
