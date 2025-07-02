from django.contrib import admin

# Register your models here.
from .models import Team, TeamMembership
admin.site.register(Team)
admin.site.register(TeamMembership)


