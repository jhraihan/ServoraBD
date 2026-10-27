from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.permissions import IsCustomer
from apps.common.exceptions import NotFound
from apps.providers.permissions import (
    ADMIN_AUTHENTICATION, IsAdminUser, IsProvider,
)

from . import selectors, services
from .serializers import (
    CustomerRatingCreateSerializer, CustomerRatingSerializer,
    HideReviewSerializer, OwnReviewSerializer, ReplyCreateSerializer,
    ReviewCreateSerializer, ReviewEditSerializer, ReviewSerializer,
)


class ProviderReviewListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ReviewSerializer

    def get_queryset(self):
        return selectors.published_reviews_for(self.kwargs["provider_id"])


class ReviewListCreateView(APIView):
    permission_classes = [IsCustomer]

    def get(self, request):
        reviews = selectors.reviews_by_customer(
            request.user.customer_profile.id
        )
        return Response(OwnReviewSerializer(reviews, many=True).data)

    def post(self, request):
        serializer = ReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        review = services.create_review(
            booking_id=data["booking"],
            customer_id=request.user.customer_profile.id,
            rating=data["rating"],
            punctuality=data.get("punctuality"),
            quality=data.get("quality"),
            professionalism=data.get("professionalism"),
            price_fairness=data.get("price_fairness"),
            comment=data.get("comment", ""),
        )
        return Response(OwnReviewSerializer(review).data,
                        status=status.HTTP_201_CREATED)


class ReviewEditView(APIView):
    permission_classes = [IsCustomer]

    def patch(self, request, review_id):
        serializer = ReviewEditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        review = services.edit_review(
            review_id=review_id,
            customer_id=request.user.customer_profile.id,
            **serializer.validated_data,
        )
        return Response(OwnReviewSerializer(review).data)


class ReviewReplyView(APIView):
    permission_classes = [IsProvider]

    def post(self, request, review_id):
        serializer = ReplyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        services.reply_to_review(
            review_id=review_id,
            provider_id=request.user.provider_profile.id,
            body=serializer.validated_data["body"],
        )
        review = selectors.review_for_provider(
            review_id, request.user.provider_profile.id,
        )
        return Response(ReviewSerializer(review).data,
                        status=status.HTTP_201_CREATED)


class MyReceivedReviewsView(ListAPIView):
    permission_classes = [IsProvider]
    serializer_class = ReviewSerializer

    def get_queryset(self):
        return selectors.published_reviews_for(
            self.request.user.provider_profile.id
        )


class CustomerRatingView(APIView):
    permission_classes = [IsProvider]

    def post(self, request):
        serializer = CustomerRatingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        record = services.rate_customer(
            booking_id=data["booking"],
            provider_id=request.user.provider_profile.id,
            rating=data["rating"],
            comment=data.get("comment", ""),
        )
        return Response(CustomerRatingSerializer(record).data,
                        status=status.HTTP_201_CREATED)


class HideReviewView(APIView):
    permission_classes = [IsAdminUser]
    authentication_classes = ADMIN_AUTHENTICATION

    def post(self, request, review_id):
        serializer = HideReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        review = services.hide_review(
            review_id=review_id,
            admin_user_id=request.user.id,
            reason=serializer.validated_data["reason"],
        )
        return Response(OwnReviewSerializer(review).data)


class UnhideReviewView(APIView):
    permission_classes = [IsAdminUser]
    authentication_classes = ADMIN_AUTHENTICATION

    def post(self, request, review_id):
        review = services.unhide_review(
            review_id=review_id, admin_user_id=request.user.id,
        )
        return Response(OwnReviewSerializer(review).data)
