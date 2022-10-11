import glob
import logging
import os

import requests
import wget
from babel.dates import format_date
from datetime import datetime
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)


class HomiliadoDia:
    def __init__(self):
        # hoje = datetime.now()
        # titulo_arquivo = "homilia_do_dia_%s" % hoje.strftime("%d_%m_%Y")
        self.date = format_date(datetime.now().date(), format='full', locale='pt_br')

        # O arquivo será salvo em /tmp/
        self.audio_mp3 = "/tmp/%s.mp3" % self.date
        self.homilia_do_dia_titulo = None
        self.homilia_do_dia_texto = None
        self.url_audio_embed = None
        self.html_pagina = requests.get("https://homilia.cancaonova.com/pb/")
        self.html_pagina_soup = BeautifulSoup(self.html_pagina.text, "lxml")
        self.homilia_iframe = BeautifulSoup(self.html_pagina.text, "lxml").find_all("iframe")
        self.audio_id = self.homilia_iframe[-1]["src"].split("id=")[1].split("&")[0]

    def obter_homilia(self):
        print(os.path.isfile(self.audio_mp3))
        self.homilia_do_dia_titulo = self.html_pagina_soup.find("h1", {"class": "entry-title"}).findChild(
            "span").text  # Texto título usado na página
        homilia_do_dia_soup = self.html_pagina_soup.find("div", {"class": "entry-content content-homilia"})
        self.homilia_do_dia_texto = homilia_do_dia_soup.text.split("\t\t")[0].strip()  # Texto da homilia

        return [f'{self.date}\n{self.homilia_do_dia_titulo}.\n\nReflexão do dia.\n{self.homilia_do_dia_texto}']

    def obter_arquivo_audio(self):
        if os.path.isfile(self.audio_mp3):
            return {'date': self.date, 'path_audio': self.audio_mp3}

        for archive in glob.glob('/tmp/*.mp3'):
            os.remove(archive)

        # Obter URL do áudio em mp3
        embed = requests.get("https://apps.cancaonova.com/embeds/EmbedsMedia/get_player/%s" % self.audio_id)
        source = BeautifulSoup(embed.text, "lxml").find("source")

        # URL
        logger.critical(source["src"])
        logger.critical('Baixando audio')
        wget.download(source["src"], self.audio_mp3)
        logger.critical('Audio baixado')
        if os.path.isfile(self.audio_mp3):
            return {'date': self.date, 'path_audio': self.audio_mp3}

# homilia_do_dia = HomiliadoDia()
# homilia_do_dia.obter_homilia()
# homilia_do_dia.obter_arquivo_audio()
