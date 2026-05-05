from django.urls import path

from phoxtail.agent import views

app_name = "phoxtail_agent"

urlpatterns = [
    path("chat-history/", views.chat_history, name="chat_history"),
]
