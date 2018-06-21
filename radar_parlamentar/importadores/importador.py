import logging
from importadores import importador_elasticsearch
from importadores.conv import ImportadorConvencao
from importadores.cmsp import ImportadorCMSP
from importadores.sen import ImportadorVotacoesSenado
from importadores.cdep import ImportadorCamara
from .importador_casa_legislativa import ImportadorCasaLegislativa

logger = logging.getLogger("radar")

def importar(importador_casa_legislativa):
    importador_casa_legislativa.main()
    importador_elasticsearch.main()

def main(lista_casas_legislativas):

    for casa_legislativa in lista_casas_legislativas:
        if casa_legislativa == 'conv':
            importador_casa_legislativa = ImportadorConvencao()
            importar(importador_casa_legislativa)

        elif casa_legislativa == 'cmsp':
            importador_casa_legislativa = ImportadorCMSP()
            importar(importador_casa_legislativa)

        elif casa_legislativa == 'sen':
            importador_casa_legislativa = ImportadorVotacoesSenado()
            importar(importador_casa_legislativa)

        elif casa_legislativa == 'cdep':
            importador_casa_legislativa = ImportadorCamara()
            importar(importador_casa_legislativa)

        else:
            logger.info("Casa %s não encontrada" % casa_legislativa)
