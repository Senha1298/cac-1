import requests

# Testa a conexão com a API de clientes
def test_api_cliente():
    telefone = "61982132603"
    api_url = f"https://webhook-manager.replit.app/api/v1/cliente?telefone={telefone}"
    
    try:
        print(f"Fazendo requisição para: {api_url}")
        response = requests.get(api_url)
        
        print(f"Status code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Resposta da API: {data}")
            
            if data.get('sucesso') and data.get('cliente'):
                cliente = data['cliente']
                print(f"Nome: {cliente.get('nome', '')}")
                print(f"CPF: {cliente.get('cpf', '')}")
                print(f"Telefone: {cliente.get('telefone', '')}")
                print(f"Email: {cliente.get('email', '')}")
                
                # Formatar o telefone
                telefone = cliente.get('telefone', '')
                if telefone and telefone.startswith('+55'):
                    telefone = telefone[3:]
                    if len(telefone) == 11:
                        telefone = f"({telefone[:2]}) {telefone[2:]}"
                    print(f"Telefone formatado: {telefone}")
            else:
                print("API não retornou sucesso ou dados do cliente")
        else:
            print(f"Erro na requisição. Status code: {response.status_code}")
            
    except Exception as e:
        print(f"Erro ao testar API: {str(e)}")

if __name__ == "__main__":
    test_api_cliente()