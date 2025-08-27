import os
import requests
import base64
import uuid
from datetime import datetime
from flask import current_app
import logging

class PagnetAPI:
    """
    API client for Pagnet Brasil PIX transactions
    """

    def __init__(self):
        self.base_url = "https://api.pagnetbrasil.com/v1"
        self.public_key = os.environ.get('PAGNET_PUBLIC_KEY')
        self.secret_key = os.environ.get('PAGNET_SECRET_KEY')

        if not self.public_key or not self.secret_key:
            current_app.logger.error("[PAGNET] Chaves de API não encontradas nas variáveis de ambiente")
            raise ValueError("PAGNET_PUBLIC_KEY e PAGNET_SECRET_KEY são obrigatórias")

        # Create Basic Auth header
        auth_string = f"{self.public_key}:{self.secret_key}"
        auth_bytes = auth_string.encode('ascii')
        auth_base64 = base64.b64encode(auth_bytes).decode('ascii')

        self.headers = {
            'Authorization': f'Basic {auth_base64}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        current_app.logger.info("[PAGNET] API client inicializada com sucesso")

    def create_pix_transaction(self, customer_data, amount, phone=None, postback_url=None):
        """
        Create a PIX transaction using Pagnet API

        Args:
            customer_data (dict): Customer information with keys: nome, cpf, email, phone
            amount (float): Transaction amount in BRL
            phone (str): Customer phone number
            postback_url (str): URL for webhook notifications

        Returns:
            dict: Transaction result with success status and PIX data
        """
        try:
            current_app.logger.info(f"[PAGNET] Iniciando criação de transação PIX - Valor: R$ {amount}")

            # Convert amount to cents
            amount_cents = int(float(amount) * 100)

            # Prepare customer data
            customer_name = customer_data.get('nome', 'Cliente')
            customer_cpf = customer_data.get('cpf', '').replace('.', '').replace('-', '').replace(' ', '')
            customer_email = customer_data.get('email', 'cliente@email.com')
            customer_phone = phone or customer_data.get('phone', '11999999999')

            # Clean phone number (only digits)
            customer_phone = ''.join(filter(str.isdigit, customer_phone))

            # Generate unique transaction ID
            transaction_id = f"PIX{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"

            current_app.logger.info(f"[PAGNET] Dados da transação: Nome={customer_name}, CPF={customer_cpf}, Valor=R${amount} ({amount_cents} centavos)")

            # Prepare the payload according to Pagnet documentation
            payload = {
                "amount": amount_cents,
                "paymentMethod": "pix",
                "pix": {
                    "expiresInDays": 3
                },
                "items": [
                    {
                        "title": "Emissão do CR",
                        "unitPrice": amount_cents,
                        "quantity": 1,
                        "tangible": False
                    }
                ],
                "customer": {
                    "name": customer_name,
                    "email": customer_email,
                    "document": {
                        "type": "cpf",
                        "number": customer_cpf
                    },
                    "phone": customer_phone
                }
            }

            # Add postback URL if provided
            if postback_url:
                payload["notificationUrl"] = postback_url

            # Add external reference
            payload["externalReference"] = transaction_id

            current_app.logger.info(f"[PAGNET] Payload preparado: {payload}")

            # Make API request
            url = f"{self.base_url}/transactions"
            current_app.logger.info(f"[PAGNET] Fazendo requisição para: {url}")

            response = requests.post(
                url,
                json=payload,
                headers=self.headers,
                timeout=30
            )

            current_app.logger.info(f"[PAGNET] Status da resposta: {response.status_code}")
            current_app.logger.info(f"[PAGNET] Cabeçalhos da resposta: {dict(response.headers)}")

            if response.status_code in [200, 201]:
                response_data = response.json()
                current_app.logger.info(f"[PAGNET] Resposta da API: {response_data}")

                # Extract PIX data from response
                pix_code = response_data.get('pix', {}).get('qrcode') or response_data.get('qrCode') or response_data.get('qrcode')
                transaction_id_response = response_data.get('id') or response_data.get('transactionId') or transaction_id

                if not pix_code:
                    current_app.logger.error(f"[PAGNET] Código PIX não encontrado na resposta: {response_data}")
                    return {
                        'success': False,
                        'error': 'Código PIX não foi gerado pela API'
                    }

                # Return successful response
                result = {
                    'success': True,
                    'transaction_id': transaction_id_response,
                    'pix_code': pix_code,
                    'amount': amount,
                    'external_reference': transaction_id,
                    'raw_response': response_data
                }

                current_app.logger.info(f"[PAGNET] ✅ Transação criada com sucesso: {transaction_id_response}")
                return result

            else:
                error_text = response.text
                current_app.logger.error(f"[PAGNET] ❌ Erro na API - Status: {response.status_code}, Resposta: {error_text}")

                try:
                    error_data = response.json()
                    error_message = error_data.get('message', error_text)
                except:
                    error_message = error_text

                return {
                    'success': False,
                    'error': f'Erro da API Pagnet: {error_message}',
                    'status_code': response.status_code
                }

        except requests.exceptions.Timeout:
            current_app.logger.error("[PAGNET] ❌ Timeout na requisição")
            return {
                'success': False,
                'error': 'Timeout na comunicação com a API'
            }

        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"[PAGNET] ❌ Erro de conexão: {e}")
            return {
                'success': False,
                'error': f'Erro de conexão: {str(e)}'
            }

        except Exception as e:
            current_app.logger.error(f"[PAGNET] ❌ Erro inesperado: {e}")
            return {
                'success': False,
                'error': f'Erro interno: {str(e)}'
            }

    def check_transaction_status(self, transaction_id):
        """
        Check the status of a PIX transaction

        Args:
            transaction_id (str): The transaction ID to check

        Returns:
            dict: Transaction status information
        """
        try:
            url = f"{self.base_url}/transactions/{transaction_id}"

            response = requests.get(
                url,
                headers=self.headers,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'status': data.get('status', 'unknown'),
                    'data': data
                }
            else:
                return {
                    'success': False,
                    'error': f'Status code: {response.status_code}'
                }

        except Exception as e:
            current_app.logger.error(f"[PAGNET] Erro ao verificar status: {e}")
            return {
                'success': False,
                'error': str(e)
            }


def create_pagnet_api():
    """Factory function to create PagnetAPI instance"""
    return PagnetAPI()