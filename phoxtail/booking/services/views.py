from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from phoxtail.booking.services.models import Service


@login_required
def services_list_view(request):
    """
    Displays a list of all available services.
    """
    services = Service.objects.all()
    context = {
        "services": services,
    }
    return render(request, "phoxtail_booking_services/list/index.html", context)


@login_required
def service_detail_view(request, service_id):
    """
    Displays the details of a specific service.
    """
    service = Service.objects.get(uuid=service_id)
    context = {
        "service": service,
    }
    return render(request, "phoxtail_booking_services/detail/index.html", context)
