from django.contrib import admin
from django.urls import path
from usine import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.accueil, name='accueil'),
    path('connexion/', views.connexion, name='connexion'),
    path('inscription/', views.inscription, name='inscription'),
    path('deconnexion/', views.deconnexion, name='deconnexion'),
    path('stocks/', views.espace_stocks, name='espace_stocks'),
    path('maintenance/', views.espace_maintenance, name='espace_maintenance'),
    path('responsable/', views.espace_responsable, name='espace_responsable'),
]