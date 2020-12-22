import re

import requests
from bs4 import BeautifulSoup


class BuscarLiturgia():
    def __init__(self, dia, mes, ano):
        # Declaração de variáveis a serem usadas para definir dia, mês e ano
        self.dia = str(dia)
        self.mes = str(mes)
        self.ano = str(ano)

    def obter_url(self):
        r_get_url_payload = {
            "action": "widget-ajax",
            "sMes": self.mes,
            "sAno": self.ano,
            "title": "",
            "type": "liturgia",
            "ajax": "true"
        }

        r_get_url = requests.post("https://liturgia.cancaonova.com/wp-admin/admin-ajax.php", data=r_get_url_payload)
        r_get_url_soap = BeautifulSoup(r_get_url.text, "lxml")

        # Obento tabela extraindo do HTML da página de resposta do request anterior
        tabela = r_get_url_soap.find("table", {"id": "wp-calendar"})
        tabela_corpo = tabela.find('tbody')

        # Dict para receber relação dia dias do mês e seus determinados links da liturgia. Ex: {'1': 'https://liturgia.cancaonova.com/etc'}
        mes_liturgia = {}

        linhas = tabela_corpo.find_all('tr')
        for linha in linhas:
            colunas = linha.find_all('td')
            for elemento in colunas:
                dia = elemento.text.strip()

                if dia != "":
                    # Se o dia tiver uma leitura (contida no href da tag <a>), adicionar ao dict o dia e o link
                    try:
                        href = elemento.find("a")["href"]
                        mes_liturgia[dia] = href
                    # Se para o dia não houver uma leitura, adicionar apenas o dia com um value vazio
                    except:
                        mes_liturgia[dia] = None

        # Se o dia (key) tiver uma leitura (value), mostrar o valor encontrado
        if mes_liturgia.get(self.dia):
            print("\nURL encontrada: %s" % mes_liturgia[self.dia])
            return self.obter_liturgia(mes_liturgia[self.dia])
        else:
            print("\nLiturgia indisponível para a data especificada")
            return False

    def obter_liturgia(self, url):
        # Aquisição da liturgia do dia através do site da Canção Nova
        liturgia_do_dia = requests.get(url)
        liturgia_do_dia_soup = BeautifulSoup(liturgia_do_dia.text, "lxml")

        dia_liturgia = liturgia_do_dia_soup.find("meta", {"property": "og:title"})["content"]
        leituras = liturgia_do_dia_soup.find_all("div", {"id": re.compile(r"liturgia-\d")})

        self.leituras_lista = []
        for leitura in leituras:
            leitura_texto = leitura.text.strip()

            # Obter primeira linha do texto para editá-la e inserir um espaçamento de linha
            leitura_texto_linhas = leitura_texto.split("\n")
            primeira_linha = leitura_texto_linhas[0]

            leitura_texto = leitura_texto.replace(primeira_linha, "%s\n" % primeira_linha)
            # print("\n%s" % leitura_texto)

            # Adicionar o dia litúrgico na primeira linha da primeira leitura
            if leituras.index(leitura) == 0:
                leitura_texto = "{}\n\n{}".format(dia_liturgia, leitura_texto)
            self.leituras_lista.append(leitura_texto)

        return self.leituras_lista
