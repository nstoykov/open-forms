import logging
from dataclasses import dataclass

from django.contrib.gis.geos import fromstr
from django.utils.translation import gettext_lazy as _

import requests
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from zds_client import ClientError

from openforms.api.serializers import ExceptionSerializer, ValidationErrorSerializer
from openforms.api.views.mixins import ListMixin
from openforms.submissions.api.permissions import AnyActiveSubmissionPermission

from ..models import KadasterApiConfig
from ..search import free_address_search, reverse_address_search
from .serializers import (
    AddressSearchResultSerializer,
    LatLngSearchInputSerializer,
    LatLngSearchResultSerializer,
)

logger = logging.getLogger(__name__)


@extend_schema(
    summary=_("Get an adress based on coordinates"),
    description=_(
        "Get the closest address name based on the given longitude and latitude."
    ),
    parameters=[
        OpenApiParameter(
            "lat",
            OpenApiTypes.FLOAT,
            OpenApiParameter.QUERY,
            description=_("The latitude of the location, in decimal degrees."),
            required=True,
        ),
        OpenApiParameter(
            "lng",
            OpenApiTypes.FLOAT,
            OpenApiParameter.QUERY,
            description=_("The longitude of the location, in decimal degrees."),
            required=True,
        ),
    ],
    responses={
        200: LatLngSearchResultSerializer,
        204: None,
        status.HTTP_400_BAD_REQUEST: ValidationErrorSerializer,
        status.HTTP_403_FORBIDDEN: ExceptionSerializer,
    },
)
class LatLngSearchView(APIView):
    authentication_classes = ()
    permission_classes = [AnyActiveSubmissionPermission]

    def get(self, request: Request):
        config = KadasterApiConfig.get_solo()
        assert isinstance(config, KadasterApiConfig)

        input_serializer = LatLngSearchInputSerializer(data=request.GET)
        input_serializer.is_valid(raise_exception=True)

        lat = input_serializer.validated_data["lat"]
        lng = input_serializer.validated_data["lng"]
        client = config.get_client()
        try:
            bag_response = reverse_address_search(client, lat, lng)
        except (ClientError, requests.RequestException):
            logger.exception(
                "Couldn't retrieve locatieserver reverse lookup data",
                extra={"lat": lat, "lng": lng},
            )
            return Response(status=status.HTTP_204_NO_CONTENT)

        if not (
            (response := bag_response.get("response"))
            and (docs := response.get("docs"))
            and (weergavenaam := docs[0].get("weergavenaam"))
        ):
            # no response with docs: return empty
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = LatLngSearchResultSerializer(
            instance={"label": weergavenaam}, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(
    summary=_("List address suggestions with coordinates."),
    description=_(
        "Get a list of addresses, ordered by relevance/match score of the input "
        "query. Note that only results having latitude/longitude data are returned.\n\n"
        "The results are retrieved from the configured geo search service, defaulting "
        "to the Kadaster location server."
    ),
    parameters=[
        OpenApiParameter(
            "q",
            OpenApiTypes.STR,
            OpenApiParameter.QUERY,
            description=_(
                "Search query for the address to retrieve suggestions with geo-information for."
            ),
            required=True,
        )
    ],
    responses={
        200: AddressSearchResultSerializer(many=True),
        status.HTTP_400_BAD_REQUEST: ValidationErrorSerializer,
        status.HTTP_403_FORBIDDEN: ExceptionSerializer,
    },
)
class AddressSearchView(ListMixin, APIView):
    authentication_classes = ()
    permission_classes = [AnyActiveSubmissionPermission]
    serializer_class = AddressSearchResultSerializer

    def get_objects(self):
        config = KadasterApiConfig.get_solo()
        assert isinstance(config, KadasterApiConfig)
        query = self.request.GET.get("q")

        if not query:
            raise serializers.ValidationError(
                {"q": _("Missing query parameter 'q'")},
                code="required",
            )

        client = config.get_client()
        try:
            bag_response = free_address_search(client, query)
        except (ClientError, requests.RequestException):
            logger.exception("couldn't retrieve pdok locatieserver data")
            return []

        if not (
            (response := bag_response.get("response"))
            and (docs := response.get("docs"))
        ):
            # no response with docs: return empty
            return []

        locations = [
            location for doc in docs if (location := _process_search_result(doc))
        ]

        return locations


def _parse_coordinates(doc: dict, key: str) -> tuple[float, float] | None:
    if not (wkt_value := doc.get(key)):
        return None
    try:
        coord0, coord1 = fromstr(
            wkt_value
        )  # we expect a two-tuple, and not any arbitrary shape
    except (ValueError, TypeError):
        logger.info("Malformed %s in location server response: %r", key, doc)
        return None
    return coord0, coord1


@dataclass
class RD:
    x: float
    y: float

    @classmethod
    def fromtuple(cls, value: tuple[float, float]):
        x, y = value
        return cls(x=x, y=y)


@dataclass
class LatLng:
    lat: float
    lng: float

    @classmethod
    def fromtuple(cls, value: tuple[float, float]):
        lng, lat = value
        return cls(lat=lat, lng=lng)


@dataclass
class Location:
    label: str
    lat_lng: LatLng
    rd: RD | None


def _process_search_result(doc: dict) -> Location | None:
    label = doc.get("weergavenaam", "")
    lat_lng = _parse_coordinates(doc, "centroide_ll")
    x_y = _parse_coordinates(doc, "centroide_rd")
    if not lat_lng:
        return None
    return Location(
        label=label,
        lat_lng=LatLng.fromtuple(lat_lng),
        # TODO: calculate rd when missing from lat_lng
        rd=RD.fromtuple(x_y) if x_y is not None else None,
    )