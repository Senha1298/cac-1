"""
SMS Service using SMSDev API
"""
import os
import logging
import requests
from typing import Dict, Any, Optional

class SMSDevService:
    """
    Service for sending SMS messages using the SMSDev API.
    Documentation: https://www.smsdev.com.br/envio-sms/
    """
    API_URL = "https://api.smsdev.com.br/v1/send"

    def __init__(self, api_key=None):
        """
        Initialize the SMSDev service with the API key
        """
        self.api_key = api_key or os.environ.get("SMSDEV_API_KEY")
        
        if not self.api_key:
            logging.warning("SMSDEV_API_KEY não configurada, o serviço de SMS não funcionará")
        else:
            logging.info("Serviço de SMS inicializado com sucesso")

    def format_phone_number(self, phone):
        """
        Format the phone number according to SMSDev requirements
        Remove any non-numeric characters and ensure it has the country code
        """
        # Remove any non-numeric characters
        phone = ''.join(filter(str.isdigit, phone))
        
        # Ensure it has Brazil country code (55)
        if not phone.startswith('55'):
            phone = '55' + phone
            
        return phone

    def send_sms(self, phone_number, message):
        """
        Send an SMS message using the SMSDev API
        
        Args:
            phone_number (str): The recipient's phone number (with country code)
            message (str): The message to be sent
            
        Returns:
            dict: The response from the SMSDev API
        """
        if not self.api_key:
            logging.error("Não foi possível enviar SMS: API key não configurada")
            return {"success": False, "error": "API key não configurada"}
            
        formatted_phone = self.format_phone_number(phone_number)
        
        # Prepare the payload for SMSDev API
        payload = {
            "key": self.api_key,
            "type": 9,  # Type 9 is for SMS messages
            "number": formatted_phone,
            "msg": message
        }
        
        try:
            logging.info(f"Enviando SMS para {formatted_phone}")
            response = requests.post(self.API_URL, params=payload)
            response_data = response.json()
            
            if response.status_code == 200:
                logging.info(f"SMS enviado com sucesso: {response_data}")
                return {"success": True, "data": response_data}
            else:
                logging.error(f"Erro ao enviar SMS: {response_data}")
                return {"success": False, "error": response_data}
                
        except Exception as e:
            logging.error(f"Exceção ao enviar SMS: {str(e)}")
            return {"success": False, "error": str(e)}

    def send_payment_confirmation(self, user_data, domain):
        """
        Send a payment confirmation SMS with a link to complete the registration
        
        Args:
            user_data (dict): User information including name and phone
            domain (str): The website domain to include in the SMS
            
        Returns:
            dict: The response from the send_sms method
        """
        name = user_data.get('full_name', '').split()[0]  # Get first name
        phone = user_data.get('phone', '')
        
        if not phone:
            logging.error("Número de telefone não fornecido para envio de SMS")
            return {"success": False, "error": "Número de telefone não fornecido"}
            
        # Ensure domain doesn't have protocol
        if domain.startswith('http://'):
            domain = domain[7:]
        elif domain.startswith('https://'):
            domain = domain[8:]
            
        # Format the message as per requirements
        message = f"EXERCITO: [FINALIZAR CAC] {name}, para finalizar o seu registro CAC, e emitir seu certificado e necessario acessar: {domain}/resultado/PAID"
        
        return self.send_sms(phone, message)

def test_sms_service():
    """
    Test function to validate the SMS service is working
    """
    service = SMSDevService()
    response = service.send_sms("5511999887766", "Teste de SMS do sistema CAC")
    print(response)
    return response

# Create a singleton instance
sms_service = SMSDevService()

if __name__ == "__main__":
    # Test the service when run directly
    test_sms_service()