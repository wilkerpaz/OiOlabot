import requests
from bs4 import BeautifulSoup

class SantodoDia():
    def buscar_santo(self):
        html_pagina = requests.get("https://santo.cancaonova.com/")
        html_pagina_soup = BeautifulSoup(html_pagina.text, "lxml")

        santo_do_dia_nome = html_pagina_soup.find("h1", {"class": "entry-title"}).findChild("span").text
        santo_do_dia_imagem = html_pagina_soup.find("img", {"class": True, "src": True})["src"]

        santo_do_dia_lista = []
        santo_do_dia_html = html_pagina_soup.find("div", {"class": "entry-content content-santo"}).findChildren("p")
        [santo_do_dia_lista.append(texto.text) for texto in santo_do_dia_html]

        santo_do_dia_texto = "\n".join(santo_do_dia_lista)
        print("Santo dia: %s\n" % santo_do_dia_nome)
        print(santo_do_dia_imagem)
        print("\n%s" % santo_do_dia_texto)