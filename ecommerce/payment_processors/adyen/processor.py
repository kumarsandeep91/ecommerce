""" Adyen payment processing. """
from __future__ import unicode_literals

from datetime import datetime
import logging
from urlparse import urljoin

from oscar.apps.payment.exceptions import GatewayError, TransactionDeclined
from oscar.core.loading import get_model
import requests

from ecommerce.core.constants import ISO_8601_FORMAT
from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.extensions.payment.processors import BasePaymentProcessor
from ecommerce.extensions.payment.utils import minor_units
from ecommerce.extensions.refund.status import REFUND
from ecommerce.payment_processors.adyen.exceptions import (
    MissingAdyenEventCodeException,
    UnsupportedAdyenEventException
)

logger = logging.getLogger(__name__)

PaymentEvent = get_model('order', 'PaymentEvent')
PaymentEventType = get_model('order', 'PaymentEventType')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
ProductClass = get_model('catalogue', 'ProductClass')
Source = get_model('payment', 'Source')
SourceType = get_model('payment', 'SourceType')


class Adyen(BasePaymentProcessor):
    """
    Adyen CSE Integration (June 2016)

    For reference, see https://docs.adyen.com/developers
    """

    CONFIGURATION_MODEL = 'ecommerce.payment_processors.adyen.models.AdyenConfiguration'
    NAME = 'adyen'
    URLS_MODULE = 'ecommerce.payment_processors.adyen.urls'

    @property
    def generation_time(self):
        return datetime.utcnow().strftime(ISO_8601_FORMAT)

    def get_transaction_parameters(self, basket, request=None):
        """
        Generate a dictionary of parameters Adyen requires to complete a transaction.

        Arguments:
            basket (Basket): The basket of products being purchase.; not used by this method.

        Keyword Arguments:
            request (Request): A Request object which could be used to construct an absolute URL; not
                used by this method.

        Returns:
            dict: Adyen-specific parameters required to complete a transaction.
        """
        parameters = {
            u'payment_page_url': '',
        }

        return parameters

    def authorise(self, basket, encryptedCardJSON):
        """
        Send authorise API request to Adyen to authorize payment.
        """
        response = requests.post(
            urljoin(self.configuration.payment_api_url, 'authorise'),
            auth=(self.configuration.web_service_username, self.configuration.web_service_password),
            headers={
                'Content-Type': 'application/json'
            },
            json={
                'additionalData': {
                    'card.encrypted.json': encryptedCardJSON
                },
                'amount': {
                    'value': minor_units(basket.total_incl_tax, basket.currency),
                    'currency': basket.currency
                },
                'reference': basket.order_number,
                'merchantAccount': self.configuration.merchant_account_code
            }
        )

        adyen_response = response.json()
        adyen_response['eventCode'] = 'AUTHORISATION'

        return adyen_response

    def handle_processor_response(self, response, basket=None):
        """
        Handle notification/response from Adyen.

        This method does the following:
            1. Create PaymentEvents and Sources for successful payments.

        Arguments:
            response (dict): Dictionary of parameters received from the payment processor.

        Keyword Arguments:
            basket (Basket): Basket being purchased via the payment processor.

        Raises:
            UserCancelled: Indicates the user cancelled payment.
            TransactionDeclined: Indicates the payment was declined by the processor.
            GatewayError: Indicates a general error on the part of the processor.
            InvalidAdyenDecision: Indicates an unknown decision value.
                Known values are ACCEPT, CANCEL, DECLINE, ERROR.
            PartialAuthorizationError: Indicates only a portion of the requested amount was authorized.
        """
        try:
            event_code = response['eventCode']
            psp_reference = response['pspReference']
            return getattr(self, '_handle_{event}'.format(event=event_code.lower()))(psp_reference, response, basket)
        except KeyError:
            raise MissingAdyenEventCodeException
        except AttributeError:
            raise UnsupportedAdyenEventException

    def _handle_authorisation(self, psp_reference, response, basket):
        """
        Handle an authorise response from Adyen.

        This method does the following:
            1. Create PaymentEvents and Sources for successful payments.

        Arguments:
            response (dict): Dictionary of parameters received from the payment processor.

        Keyword Arguments:
            basket (Basket): Basket being purchased via the payment processor.

        Raises:
            UserCancelled: Indicates the user cancelled payment.
            TransactionDeclined: Indicates the payment was declined by the processor.
            GatewayError: Indicates a general error on the part of the processor.
            InvalidAdyenDecision: Indicates an unknown decision value.
                Known values are ACCEPT, CANCEL, DECLINE, ERROR.
            PartialAuthorizationError: Indicates only a portion of the requested amount was authorized.
        """

        # Raise an exception for payments that were not accepted. Consuming code should be responsible for handling
        # and logging the exception.
        result_code = response['resultCode'].lower()
        if result_code != 'authorised':
            raise TransactionDeclined

        # Create Source to track all transactions related to this processor and order
        source_type, __ = SourceType.objects.get_or_create(name=self.NAME)
        currency = basket.currency
        total = basket.total_incl_tax

        source = Source(source_type=source_type,
                        currency=currency,
                        amount_allocated=total,
                        amount_debited=total,
                        reference=psp_reference)

        # Create PaymentEvent to track
        event_type, __ = PaymentEventType.objects.get_or_create(name=PaymentEventTypeName.PAID)
        event = PaymentEvent(event_type=event_type, amount=total, reference=psp_reference, processor_name=self.NAME)

        return source, event

    def _handle_cancel_or_refund(self, psp_reference, response, basket):
        order = basket.order_set.first()
        # TODO Update this if we ever support multiple payment sources for a single order.
        source = order.sources.first()
        refund = order.refunds.get(status__in=[REFUND.PENDING_WITH_REVOCATION, REFUND.PENDING_WITHOUT_REVOCATION])
        amount = refund.total_credit_excl_tax
        if response.get('success'):
            source.refund(amount, reference=psp_reference)
            revoke_fulfillment = refund.status == REFUND.PENDING_WITH_REVOCATION
            refund.set_status(REFUND.PAYMENT_REFUNDED)
            refund.complete(revoke_fulfillment)
            event_type, __ = PaymentEventType.objects.get_or_create(name=PaymentEventTypeName.REFUNDED)
            PaymentEvent.objects.create(
                event_type=event_type,
                order=order,
                amount=amount,
                reference=psp_reference,
                processor_name=self.NAME
            )
        else:
            raise GatewayError(
                'Failed to issue Adyen credit for order [{order_number}].'.format(
                    order_number=order.number
                )
            )

    def issue_credit(self, source, amount, currency):
        order = source.order

        response = requests.post(
            urljoin(self.configuration.payment_api_url, 'cancelOrRefund'),
            auth=(self.configuration.web_service_username, self.configuration.web_service_password),
            headers={
                'Content-Type': 'application/json'
            },
            json={
                'merchantAccount': self.configuration.merchant_account_code,
                'originalReference': source.reference,
                'reference': order.number
            }
        )

        adyen_response = response.json()

        try:
            if response.status_code == requests.codes.ok:
                self.record_processor_response(
                    response.json(),
                    transaction_id=adyen_response['pspReference'],
                    basket=order.basket
                )
                if adyen_response['response'] != '[cancelOrRefund-received]':
                    raise GatewayError
            else:
                raise GatewayError
        except GatewayError:
            msg = 'An error occurred while attempting to issue a credit (via Adyen) for order [{}].'.format(
                order.number
            )
            logger.exception(msg)
            raise GatewayError(msg)

        return False
