from modelagem import models
import bz2
import os
import xml.etree.ElementTree as etree
import logging

MODULE_DIR = os.path.abspath(os.path.dirname(__file__))
logger = logging.getLogger("radar")

class AcessoXMLChefesExecutivos(object):
    
    def abrir_xml(self, xml_file):
        xml_chefes = os.path.join(MODULE_DIR, xml_file)
        file = bz2.open(xml_chefes, mode='rt')
        xml = file.read()
        file.close()
        return etree.fromstring(xml)    


class ImportadorChefesExecutivos:

    def __init__(self, nome_curto_casa, tag_cargo, tag_titulo, xml_file):
        self.casa = models.CasaLegislativa.objects.get(
            nome_curto=nome_curto_casa)
        self.tag_cargo = tag_cargo
        self.tag_titulo = tag_titulo
        self.xml_file = xml_file
        self.xml = AcessoXMLChefesExecutivos()
        

    def importar_chefes(self):
        tree = self.xml.abrir_xml(self.xml_file)
        presidentes_tree = tree.find(self.tag_cargo)
        self.presidente_from_tree(presidentes_tree)

    def presidente_from_tree(self, presidentes_tree):
        for presidente in presidentes_tree.getchildren():
            if presidente.tag == self.tag_titulo:
                dado_presidente = {}
                dado_presidente['nome'] = presidente.get('Nome')
                dado_presidente['sigla_partido'] = presidente.get('Partido')
                dado_presidente['ano_inicio'] = int(presidente.get('AnoInicio'))
                dado_presidente['ano_fim'] = int(presidente.get('AnoFinal'))
                dado_presidente['genero'] = presidente.get('Genero')
                self.criar_chefe_executivo(dado_presidente)

    def criar_chefe_executivo(self, dado_presidente):
        partido = models.Partido()
        partido = partido.from_nome(dado_presidente['sigla_partido'])

        chefe = models.ChefeExecutivo(nome=dado_presidente['nome'], partido=partido,
                                      mandato_ano_inicio=dado_presidente['ano_inicio'],
                                      mandato_ano_fim=dado_presidente['ano_fim'], genero=dado_presidente['genero'])

        self.salvar_chefe_executivo(chefe)

    def salvar_chefe_executivo(self, chefe):
        # chefe_atual é recebido para adicionarmos relacão com outra casa
        chefe_atual = self.get_chefe_executivo_do_banco(chefe)

        ''' Adiciona novo chefe ou adiciona casa a um chefe ja
        existente ou ignora chefe ja existente de acordo com chefe_existe'''
        if (chefe_atual):
            if self.verifica_casa_existe_no_chefe(chefe_atual):
                logger.warn('Chefe %s já existe' % chefe.nome)
            else:
                chefe_atual.casas_legislativas.add(self.casa)
                logger.info(
                    'Adicionando chefe %s em outra casa' % chefe_atual.nome)
        else:
            chefe.save()
            chefe.casas_legislativas.add(self.casa)
            logger.info('Adicionando chefe %s' % chefe.nome)

    def get_chefe_executivo_do_banco(self, chefe):
        chefe_banco = models.ChefeExecutivo.objects.filter(
            nome=chefe.nome,
            mandato_ano_inicio=chefe.mandato_ano_inicio,
            mandato_ano_fim=chefe.mandato_ano_fim)

        if chefe_banco and chefe_banco[0].partido.pk == chefe.partido.pk:
            return chefe_banco[0]
        else:
            return None

    def verifica_casa_existe_no_chefe(self, chefe_atual):

        for index in range(len(chefe_atual.casas_legislativas.all())):
            # Quer dizer que o chefe ja tem a casa atual
            if(chefe_atual.casas_legislativas.all()[index] == self.casa):
                return True
                break
        return False
