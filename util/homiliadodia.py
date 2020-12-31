import glob
import json
import re
import uuid
import base64
import time
import subprocess
import os

import requests
from babel.dates import format_date
from datetime import datetime
from bs4 import BeautifulSoup


class HomiliadoDia:
    def __init__(self):
        # hoje = datetime.now()
        # titulo_arquivo = "homilia_do_dia_%s" % hoje.strftime("%d_%m_%Y")
        titulo_arquivo = "homilia_do_dia"


        # O arquivo será salvo em /tmp/
        self.date = format_date(datetime.now().date(), format='full', locale='pt_br')
        self.audio_ts = "/tmp/%s.ts" % titulo_arquivo
        self.audio_aac = "/tmp/%s.aac" % titulo_arquivo
        self.homilia_do_dia_titulo = None
        self.homilia_do_dia_texto = None
        self.url_audio_embed = None
        self.html_pagina = requests.get("https://homilia.cancaonova.com/pb/")
        self.html_pagina_soup = BeautifulSoup(self.html_pagina.text, "lxml")
        self.url_audio_embed = \
            self.html_pagina_soup.find("iframe",
                                       {"src": True, "style": "overflow:hidden;", "class": "iframe_embed"})["src"]

    def obter_homilia(self):
        self.homilia_do_dia_titulo = self.html_pagina_soup.find("h1", {"class": "entry-title"}).findChild(
            "span").text  # Texto título usado na página
        homilia_do_dia_soup = self.html_pagina_soup.find("div", {"class": "entry-content content-homilia"})
        self.homilia_do_dia_texto = homilia_do_dia_soup.text.split("\t\t")[0].strip()  # Texto da homilia

        return [f'{self.date}\n{self.homilia_do_dia_titulo}.\n\nReflexão do dia.\n{self.homilia_do_dia_texto}']

    def obter_arquivo_audio(self):
        if os.path.isfile(self.audio_aac):
            return {'date': self.date, 'path_audio': self.audio_aac}

        for archive in glob.glob('/tmp/*.aac'):
            os.remove(archive)

        audio_play_info = None
        html_embed = requests.get(self.url_audio_embed)
        html_embed_soup = BeautifulSoup(html_embed.text, "lxml").find("iframe")["src"]

        # Regex para obter algumas informações da URL a serem usadas no request do m3u8
        match_r = re.search(r"(?:/p/(\d+))(?:/sp/(\d+))", html_embed_soup)
        p_id = match_r.group(1)
        sp_id = match_r.group(2)

        # Obter informações contidas em javascript da página
        response_embed = requests.get(html_embed_soup)
        response_embed_soup = BeautifulSoup(response_embed.text, "lxml").find_all("script", {"type": "text/javascript"})

        for script in response_embed_soup:
            if 'window.kalturaIframePackageData' in str(script):
                audio_play_info = str(script)
                break

        # Obter dict a partir do javascript encontrado
        if audio_play_info:
            audio_play_info = audio_play_info.split(" = {")[1].split("};\n")[0]
            audio_play_info_json = json.loads("{%s}" % audio_play_info)

            # Variáveis a serem usadas no request do m3u8
            uiconf_id = audio_play_info_json["playerConfig"]["uiConfId"]
            uid = str(uuid.uuid4())
            timestamp = str(round(time.time() * 1000))

            select_asset = None
            for asset in audio_play_info_json["entryResult"]["contextData"]["flavorAssets"]:
                if asset["tags"] == "mobile,web,mbr,ipad,ipadnew,iphone,iphonenew,dash":
                    select_asset = asset

            if select_asset:
                entry_id = select_asset["entryId"]
                flavor_id = select_asset["id"]
                refer_b64 = base64.b64encode("https://cdnapisec.kaltura.com".encode()).decode()

                # Request do m3u8 para download do áudio
                r_m3u8_params = {
                    "referrer": refer_b64,
                    "playSessionId": uid,
                    "clientTag": "html5:v2.53.2",
                    "uiConfId": uiconf_id,
                    "responseFormat": "jsonp",
                    "callback": "jQuery111109749039138003053_%s" % timestamp,
                    "_": timestamp,
                }

                r_m3u8 = requests.get(
                    "https://cdnapisec.kaltura.com/p/{}/sp/{}/playManifest/entryId/{}/flavorIds/{}/format/applehttp/protocol/https/a.m3u8".format(
                        p_id, sp_id, entry_id, flavor_id), params=r_m3u8_params)
                r_m3u8_json = r_m3u8.text.split("(")[1].split(")")[0]
                r_m3u8_json = json.loads(r_m3u8_json)

                m3u8_url = r_m3u8_json["flavors"][0]["url"]
                m3u8_url_streamlink = "hls://%s" % m3u8_url  # Formato usado no streamlink para reconhecer o plugin HLS

                # Se já existir o arquivo de destinado, o mesmo será deletado
                if os.path.isfile(self.audio_ts):
                    os.remove(self.audio_ts)
                if os.path.isfile(self.audio_aac):
                    os.remove(self.audio_aac)

                # Download do arquivo usando o streamlink (por ser mais rápido que o ffmpeg no download)
                streamlink = '/nix/store/vlr51lb5pqvxyr951506bl1xbnnpkc71-home-manager-path/bin/streamlink'
                subprocess.run([streamlink, m3u8_url_streamlink, "best", "-o", self.audio_ts, "--quiet"])
                # Conversão e fix do arquivo para aac
                ffmpeg = '/nix/store/vlr51lb5pqvxyr951506bl1xbnnpkc71-home-manager-path/bin/ffmpeg'
                subprocess.run([ffmpeg, "-i", self.audio_ts, "-c", "copy", self.audio_aac, "-loglevel", "quiet"])
                os.remove(self.audio_ts)
                if os.path.isfile(self.audio_aac):
                    return {'date': self.date, 'path_audio': self.audio_aac}


# homilia_do_dia = HomiliadoDia()
# homilia_do_dia.obter_homilia()
# homilia_do_dia.obter_arquivo_audio()
