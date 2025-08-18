from django.urls import path
from .views import (
    BookReservationView,
    ReservationCancelView,
    ReservationPickupView,
    UserReservationsView,
)

urlpatterns = [
    path("", BookReservationView.as_view(), name='book-reservation'),
    path("<int:reservation_id>/cancel/", ReservationCancelView.as_view(), name='cancel-reservation'),
    path("<int:reservation_id>/pickup/", ReservationPickupView.as_view(), name='pickup-reservation'),
    path("my-reservations/", UserReservationsView.as_view(), name='my-reservations'),
]