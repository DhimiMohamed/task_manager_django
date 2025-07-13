from django.contrib import admin

# Register your models here.
from .models import Team, TeamInvitation, TeamMembership
admin.site.register(Team)
admin.site.register(TeamMembership)
admin.site.register(TeamInvitation)


