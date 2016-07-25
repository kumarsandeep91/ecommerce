define([
        'jquery',
        'jquery-ajax-retry',
        'js/views/receipt_view'
    ],
    function ($, AjaxRetry, ReceiptView) {
        'use strict';
        describe('receipt view', function() {
            var data, providerResponseData, mockRequests, mockRender, partnerResponseData;

            // mockRequests = function(requests, method, apiUrl, responseData) {
            //      AjaxHelpers.expectRequest(requests, method, apiUrl);
            //      AjaxHelpers.respondWithJson(requests, responseData);
            // };

            mockRender = function(isVerified) {
                var requests, view, orderUrlFormat;
                //requests = AjaxHelpers.requests(this);
                $("#receipt-container").data("verified", isVerified);
                view = new ReceiptView();
                view.useEcommerceApi = true;
                view.ecommerceOrderNumber = 'EDX-123456';
                orderUrlFormat = '/api/v2/orders/EDX-123456/';
                view.render();
                // mockRequests(requests, 'GET', orderUrlFormat, data);
                //
                // mockRequests(requests, 'GET', '/api/v2/partners/1/', partnerResponseData);
                //
                // mockRequests(requests, 'GET', 'https://www.edx.org/api/credit/v1/providers/edx/', providerResponseData);
                return view;
            };

            beforeEach(function() {
                var receiptFixture, providerFixture;
                // Stub analytics tracking
                window.analytics = jasmine.createSpyObj('analytics', ['page', 'track', 'trackLink']);

                loadFixtures('templates/oscar/checkout/receipt.html');

                receiptFixture = readFixtures('templates/oscar/checkout/receipt.underscore');
                providerFixture = readFixtures('templates/oscar/checkout/provider.underscore');
                appendSetFixtures(
                    '<script id=\"receipt-tpl\" type=\"text/template\" >' + receiptFixture + '</script>' +
                    '<script id=\"provider-tpl\" type=\"text/template\" >' + providerFixture + '</script>'
                );

                data = {
                    "status": "Open",
                    "billed_to": {
                        "city": "dummy city",
                        "first_name": "john",
                        "last_name": "doe",
                        "country": "AL",
                        "line2": "line2",
                        "line1": "line1",
                        "state": "",
                        "postcode": "12345"
                    },
                    "lines": [
                        {
                            "status": "Open",
                            "unit_price_excl_tax": "10.00",
                            "product": {
                                "attribute_values": [
                                    {
                                        "name": "certificate_type",
                                        "value": "verified"
                                    },
                                    {
                                        "name": "course_key",
                                        "code": "course_key",
                                        "value": "course-v1:edx+dummy+2015_T3"
                                    },
                                    {
                                        "name": "credit_provider",
                                        "value": "edx"
                                    }
                                ],
                                "stockrecords": [
                                    {
                                        "price_currency": "USD",
                                        "product": 123,
                                        "partner_sku": "1234ABC",
                                        "partner": 1,
                                        "price_excl_tax": "10.00",
                                        "id": 123
                                    }
                                ],
                                "product_class": "Seat",
                                "title": "Dummy title",
                                "url": "https://ecom.edx.org/api/v2/products/123/",
                                "price": "10.00",
                                "expires": null,
                                "is_available_to_buy": true,
                                "id": 123,
                                "structure": "child"
                            },
                            "line_price_excl_tax": "10.00",
                            "description": "dummy description",
                            "title": "dummy title",
                            "quantity": 1
                        }
                    ],
                    "number": "EDX-123456",
                    "date_placed": "2016-01-01T01:01:01Z",
                    "currency": "USD",
                    "total_excl_tax": "10.00"
                };
                partnerResponseData = {
                        "id": 1,
                        "name": "Open edX",
                        "short_code": "edX",
                        "catalogs": "https://ecom.edx.org/api/v2/partners/1/catalogs/",
                        "products": "https://ecom.edx.org/api/v2/partners/1/products/"
                };
                providerResponseData = {
                        "id": "edx",
                        "display_name": "edX",
                        "url": "http://www.edx.org",
                        "status_url": "http://www.edx.org/status",
                        "description": "Nothing",
                        "enable_integration": false,
                        "fulfillment_instructions": "",
                        "thumbnail_url": "http://edx.org/thumbnail.png"
                };
            });

            it('sends analytic event when verified receipt is rendered', function() {
                mockRender('True');
                expect(window.analytics.track).toHaveBeenCalledWith(
                    'Completed Order',
                    {
                        orderId: 'EDX-123456',
                        total: '10.00',
                        currency: 'USD'
                    }
                );

            });

            it('sends analytic event when non verified receipt is rendered', function() {
                mockRender('False');
                expect(window.analytics.track).toHaveBeenCalledWith(
                    'Completed Order',
                    {
                        orderId: 'EDX-123456',
                        total: '10.00',
                        currency: 'USD'
                    }
                );

            });

            it('renders receipt order information correctly given an order number', function() {
                var view;

                view = mockRender('True');
                expect(view.$('.order-number-heading').text()).toContain('EDX-123456');
                expect(view.$('.value-amount').text()).toContain('10.00');
            });

            it('renders partner information correctly given an order number', function () {
                var view;

                view = mockRender('True');
                expect(view.$('.partner').text()).toContain('Open edX');
            });
        });
    }
);
