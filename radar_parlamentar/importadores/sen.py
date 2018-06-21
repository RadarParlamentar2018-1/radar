# Copyright (C) 2012, Leonardo Leite
#
# This file is part of Radar Parlamentar.
#
# Radar Parlamentar is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Radar Parlamentar is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Radar Parlamentar.  If not, see <http://www.gnu.org/licenses/>.

"""módulo senado

Classes:
    CasaLegislativaGerador
    ImportadorVotacoesSenado
"""

from datetime import date
from modelagem import models
from requests.exceptions import RequestException
from django.core.exceptions import ObjectDoesNotExist
from .chefes_executivos import ImportadorChefesExecutivos
from .importador_casa_legislativa import ImportadorCasaLegislativa
from pathlib import Path
import bz2
import re
import os
import sys
import xml.etree.ElementTree as etree
import logging
import requests

MODULE_DIR = os.path.abspath(os.path.dirname(__file__))

# pasta com os arquivos com os dados fornecidos pelo senado
DATA_FOLDER = os.path.join(MODULE_DIR, 'dados/senado')
VOTACOES_FOLDER = os.path.join(DATA_FOLDER, 'votacoes')

NOME_CURTO = 'sen'
NOME_EXTENSO = 'Senado'
PARTIDO_PT = 13
SEM_PARTIDO = 0
STATUS_SUCESSO = 200

XML_FILE = 'dados/chefe_executivo/chefe_executivo_congresso.xml.bz2'

ANO_MIN = 2003

logger = logging.getLogger("radar")


class CasaLegislativaGerador:

    def gera_senado(self):
        """Gera objeto do tipo CasaLegislativa representando o Senado"""

        if not models.CasaLegislativa.objects.filter(nome_curto=NOME_CURTO):
            sen = models.CasaLegislativa()
            sen.nome = NOME_EXTENSO
            sen.nome_curto = NOME_CURTO
            sen.esfera = models.FEDERAL
            sen.save()
        else:
            sen = models.CasaLegislativa.objects.get(nome_curto=NOME_CURTO)
        return sen


class ImportadorVotacoesSenado(ImportadorCasaLegislativa):

    """Salva os dados dos arquivos XML do senado no banco de dados"""

    def __init__(self):
        self.senado = models.CasaLegislativa.objects.get(nome_curto=NOME_CURTO)
        self.parlamentares = self._init_parlamentares()
        self.proposicoes = self._init_proposicoes()

    def _init_parlamentares(self):
        """retorna dicionário
           (nome_parlamentar, nome_partido, localidade) -> Parlamentar"""
        parlamentares = {}
        for p in models.Parlamentar.objects.filter(
                casa_legislativa=self.senado):
            parlamentares[self._key(p)] = p
        return parlamentares

    def _key(self, parlamentar):
        return (parlamentar.nome,
                parlamentar.partido.nome,
                parlamentar.localidade)

    def _init_proposicoes(self):
        """retorna dicionário "sigla num/ano" -> Proposicao"""
        proposicoes = {}
        for p in models.Proposicao.objects.filter(
                casa_legislativa=self.senado):
            proposicoes[p.nome()] = p
        return proposicoes

    def _converte_data(self, data_str):
        """Converte string "aaaa-mm-dd para objeto datetime;
        retona None se data_str é inválido"""
        DATA_REGEX = '(\d{4})-(\d{2})-(\d{2})'
        res = re.match(DATA_REGEX, data_str)
        if res:
            return date(int(res.group(1)), int(res.group(2)),
                        int(res.group(3)))
        else:
            raise ValueError

    def _voto_senado_to_model(self, voto):
        """Interpreta voto como tá no XML e responde em adequação a modelagem
        em models.py"""

        DESCULPAS = ['MIS', 'MERC', 'P-NRV', 'REP',
                     'AP', 'LA', 'LAP', 'LC', 'LG', 'LS', 'NA']

        # XML não tá em UTF-8, acho q vai dar probema nessas comparações!
        voto_dict = {
            'Não': models.NAO, 'Sim': models.SIM,
            'NCom': models.AUSENTE, 'Abstenção': models.ABSTENCAO,
            'P-OD': models.ABSTENCAO
        }
        if voto in voto_dict:
            return voto_dict.get(voto)
        elif voto in DESCULPAS:
            return models.AUSENTE

        return models.ABSTENCAO

    def _find_partido(self, nome_partido):
        nome_partido = nome_partido.strip()
        partido = models.Partido.from_nome(nome_partido)
        if partido is None:
            logger.warning('Não achou o partido %s' % nome_partido)
            partido = models.Partido.get_sem_partido()
        return partido

    def _create_parlamentar(self, parlamentar_list_info):
        senador = models.Parlamentar()
        senador.id_parlamentar = parlamentar_list_info[0]
        senador.nome = parlamentar_list_info[1]
        senador.genero = parlamentar_list_info[2]
        senador.casa_legislativa = self.senado
        senador.partido = parlamentar_list_info[3]
        senador.localidade = parlamentar_list_info[4]
        senador.save()
        return senador

    def _find_parlamentar(self, voto_parlamentar_tree):
        nome_senador = voto_parlamentar_tree.find('NomeParlamentar').text
        nome_partido = voto_parlamentar_tree.find('SiglaPartido').text
        localidade = voto_parlamentar_tree.find('SiglaUF').text
        partido = self._find_partido(nome_partido)
        key = (nome_senador, partido.nome, localidade)
        if key in self.parlamentares:
            senador = self.parlamentares[key]
        else:
            codigo = voto_parlamentar_tree.find('CodigoParlamentar').text
            sexo = voto_parlamentar_tree.find('SexoParlamentar').text
            parlamentar_infos = [
                codigo, nome_senador,
                sexo, partido, localidade]
            senador = self._create_parlamentar(parlamentar_infos)
            self.parlamentares[key] = senador
            self.progresso()
        return senador

    def _create_voto(self, senador, opcao_voto, votacao):
        """Cria voto e salva no BD
           Retorna novo voto criado
        """
        voto = models.Voto()
        voto.parlamentar = senador
        voto.votacao = votacao
        voto.opcao = opcao_voto
        voto.save()
        return voto

    def _votos_from_tree(self, votos_tree, votacao):
        """Faz o parse dos votos, salva no BD e devolve lista de votos
           Retorna lista dos votos salvos
        """
        votos = []
        for voto_parlamentar_tree in votos_tree:
            senador = self._find_parlamentar(voto_parlamentar_tree)
            opcao_voto = self._voto_senado_to_model(
                voto_parlamentar_tree.find('Voto').text)
            voto = self._create_voto(senador, opcao_voto, votacao)
            votos.append(voto)
        return votos

    def _nome_prop_from_tree(self, votacao_tree):

        sigla = votacao_tree.find('SiglaMateria').text
        numero = votacao_tree.find('NumeroMateria').text
        ano = votacao_tree.find('AnoMateria').text
        return '%s %s/%s' % (sigla, numero, ano)

    def _create_prop(self, votacao_tree):
        """Cria proposicao e salva no BD
           Retorna nova proposicao criada
        """
        prop = models.Proposicao()
        prop.sigla = votacao_tree.find('SiglaMateria').text
        prop.numero = votacao_tree.find('NumeroMateria').text
        prop.ano = votacao_tree.find('AnoMateria').text
        prop.casa_legislativa = self.senado
        prop.save()
        return prop

    def _proposicao_from_tree(self, votacao_tree):

        prop_nome = self._nome_prop_from_tree(votacao_tree)
        if prop_nome in self.proposicoes:
            prop = self.proposicoes[prop_nome]
        else:
            prop = self._create_prop(votacao_tree)
            self.proposicoes[prop_nome] = prop
        return prop

    def _read_xml(self, xml_file):
        """Salva no banco de dados do Django e retorna lista das votações"""

        tree = None
        with bz2.open(xml_file, mode='rt', encoding="iso-8859-1") as f:
            tree = etree.fromstring(f.read())
        return tree

    def _find_the_votacao_code(self, votacao_tree):
        codigo = votacao_tree.find('CodigoSessaoVotacao').text
        return codigo

    def _code_exists_in_votacao_in_model(self, votacao_tree):
        codigo = self._find_the_votacao_code(votacao_tree)
        votacoes_query = models.Votacao.objects.filter(id_vot=codigo)
        if votacoes_query:
            return True, votacoes_query
        else:
            return False, votacoes_query

    def _creating_votacao(self, votacao_tree):
        proposicao = self._proposicao_from_tree(votacao_tree)
        self.progresso()
        votacao = models.Votacao()
        votacao.id_vot = self._find_the_votacao_code(votacao_tree)
        # save só pra criar a chave primária e poder atribuir os votos
        votacao.save()

        return votacao

    def _setting_votacao(self, votacao_tree):
        votacao = self._creating_votacao(votacao_tree)

        result_tree = votacao_tree.find('Resultado')
        if result_tree is not None:
            votacao.resultado = votacao_tree.find('Resultado').text

        votacao.proposicao = self._proposicao_from_tree(votacao_tree)

        return votacao

    def _check_null_votos_tree(self, votos_tree, votacao):
        if votos_tree is None:
            logger.warn(
                'Votação desconsiderada (votos_tree nulo)')
            votacao.delete()
            return True
        return False

    def _check_null_votos(self, votos_tree, votacao):
        votos = self._votos_from_tree(votos_tree, votacao)
        if not votos:
            logger.warn('Votação desconsiderada (sem votos)')
            votacao.delete()
            return True
        return False

    def _save_votacao(self, votacao_tree, votacao):
        '''setando atributos da votação a serem
          salvos caso ela não seja nula e tenha votos'''
        votacao.descricao = votacao_tree.find(
            'DescricaoVotacao').text
        votacao.data = self._converte_data(
            votacao_tree.find('DataSessao').text)
        votacao.save()
        return True, votacao

    def _add_votacao_to_model(self, votacao_tree):

        votacao = self._setting_votacao(votacao_tree)
        votos_tree = votacao_tree.find('Votos')

        # In case there is no votos_tree, gives a warning and return.
        if self._check_null_votos_tree(votos_tree, votacao):
            return False, None

        # In case there is no votos, gives a warning and return.
        if self._check_null_votos(votos_tree, votacao):
            return False, None

        if self._save_votacao(votacao_tree, votacao):
            return True, votacao

    def _check_success_state_and_votacao(self, sucess_status, votacao, votacoes):
        if sucess_status is True and votacao is not None:
            votacoes.append(votacao)

    def _append_votacao_if_code_exists_in_model(self, votacao_tree):
        votacoes = []
        # caso o codigo já exista na model
        _, votacoes_query = self._code_exists_in_votacao_in_model(
            votacao_tree)
        if votacoes_query:
            votacao = votacoes_query[0]
            votacoes.append(votacao)
        else:
            sucess_status = self._add_votacao_to_model(votacao_tree)
            votacao = sucess_status
            self._check_success_state_and_votacao(sucess_status, votacao, votacoes)
        return votacoes

    def _check_is_not_votacao_or_secreta(self, votacao_tree, votacao_secreta):
        votacoes = []
        if votacao_tree.tag == 'Votacao' and votacao_secreta == 'N':
            votacoes = self._append_votacao_if_code_exists_in_model(votacao_tree)
        return votacoes

    def _save_votacoes_in_db(self, xml_text):
        tree = etree.fromstring(xml_text)

        votacoes = []
        # Pelo q vimos, nesses XMLs não há votações 'inúteis' (homenagens etc)
        # como na cmsp (exceto as secretas)
        votacoes_tree = tree.find('Votacoes')
        # caso a árvore de votações seja vazia, a função é encerrada
        if votacoes_tree is None:
            return votacoes
        for votacao_tree in votacoes_tree:
            votacao_secreta = votacao_tree.find('Secreta').text
            votacoes = self._check_is_not_votacao_or_secreta(votacao_tree, votacao_secreta)

        return votacoes

    def progresso(self):
        """Indica progresso na tela"""
        sys.stdout.write('x')
        sys.stdout.flush()

    def _xml_file_names(self):
        """Retorna uma lista com as urls dos arquivos XMLs disponíveis
        na API do Senado"""
        xmls = []
        XML_URL = ("http://legis.senado.leg.br/dadosabertos/dados"
                   "/ListaVotacoes{ano}.xml")
        ano_atual = date.today().year
        for ano in range(ANO_MIN, ano_atual+1):
            xmls.append(XML_URL.format(ano=ano))
        return xmls

    def importar_votacoes(self):
        """# Realiza a consulta a API do senado através de uma request e
        retorna os arquivos XMLS referentes as votações para serem importados
        pelo radar
         # facilita debug"""
        list_xml = self._xml_file_names()
        for xml_url in list_xml:
            try:
                response = requests.get(xml_url)
                if response.status_code == STATUS_SUCESSO:
                    xml_text = response.text
                    logger.debug('Importando %s' % xml_url)
                    self._save_votacoes_in_db(xml_text)
                else:
                    logger.info("XML indisponível: %s" % xml_url)
            except RequestException as error:
                logger.error("%s ao acessar %s" % (error, xml_url))

    def main(self):
        logger.info('IMPORTANDO DADOS DO SENADO')
        geradorCasaLeg = CasaLegislativaGerador()
        geradorCasaLeg.gera_senado()
        logger.info('IMPORTANDO CHEFES EXECUTIVOS DO SENADO')
        importer_chefe = ImportadorChefesExecutivos(
            NOME_CURTO, 'Presidentes', 'Presidente', XML_FILE)
        importer_chefe.importar_chefes()
        logger.info('IMPORTANDO VOTAÇÕES DO SENADO')
        self.importar_votacoes()
        logger.info('PROCESSAMENTO PÓS-IMPORTAÇÃO')
        posImportacao = PosImportacao()
        posImportacao.processar()
        logger.info('IMPORTANDO INDICES DO SENADO')
        import importadores.sen_indexacao as indexacao_senado
        indexacao_senado.indexar_proposicoes()


class PosImportacao:

    def processar(self):
        self.consertar_suplicy_sem_partido()

    # Issue #325
    def consertar_suplicy_sem_partido(self):
        try:
            suplicy_sem_partido = models.Parlamentar.objects.get(
                nome='Eduardo Suplicy',
                partido__numero=SEM_PARTIDO,
                casa_legislativa__nome_curto='sen')
            suplicy_do_pt = models.Parlamentar.objects.get(
                nome='Eduardo Suplicy',
                partido__numero=PARTIDO_PT,
                casa_legislativa__nome_curto='sen')
            votos = models.Voto.objects.filter(parlamentar=suplicy_sem_partido)
            for v in votos:
                v.parlamentar = suplicy_do_pt
                v.save()
            suplicy_sem_partido.delete()
        except ObjectDoesNotExist:
            logger.warn('Eduardo Suplicy sem partido não existe.')
