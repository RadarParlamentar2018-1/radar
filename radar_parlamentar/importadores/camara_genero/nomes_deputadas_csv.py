# -*- coding:UTF-8 -*-

from os import listdir
from xml.dom.minidom import parseString

DIRETORIO = "bios"
ARQUIVO_SAIDA = "saida.csv"

TAGS = {
        'nome_txt': 'TXTNOME',
        'data': 'DATA_RECORD',
        'mandato': 'MANDATOSCD'
}

GENERO = {
            'masculino': 'M',
            'feminino': 'F'
}

class NomesDeputadas:
    def __init__(self):
        self.numero_deputadas = 0

    def main(self):
        arquivos = listdir(DIRETORIO)
        saida = open(ARQUIVO_SAIDA, "w")
        for arquivo in arquivos:
                ponteiro = open(DIRETORIO+"/"+ arquivo)
                data = ponteiro.read()
                dom = parseString(data)
                records = dom.getElementsByTagName(TAGS['data'])
                self.copiar_dados_deputados(records)
        print(self.numero_deputadas)

    def copiar_dados_deputados(self):
        for record in records:
            informacoes = self.obter_informacoes_deputado(record)
            self.escrever_saida(informacoes['nome'], informacoes['genero'], informacoes['legis'])

    def obter_informacoes_deputado(self, records):
            deputado = record.getElementsByTagName(TAGS['mandato'])[0].firstChild.data
            genero = self.obter_genero(deputado)
            nome = record.getElementsByTagName(TAGS['nome_txt'])[0].firstChild.data
            legis = record.getElementsByTagName(TAGS['mandato'])[0].firstChild.data
            legis = legis.split(";")

            informacoes = {'nome': nome, 'genero': genero, 'legis': legis}
            return informacoes

    def escrever_saida(nome, genero, legis):
        for leg in legis:
            saida_legis = ""
            dados = leg.split(",")
            ano = dados[1]
            saida_legis += "%s/" % ano
            try:
                estado = dados[2]
                saida_legis += "%s/" % estado
                partido = dados[3].partition(".")[0]
                saida_legis += "%s/" % partido
                saida_legis += " , "
            except:
                print(dados)
                saida_legis += " , "
        saida.write('%s|%s|%s\n' % (nome, genero, saida_legis))

    def obter_genero(deputado):
        if deputado.find("Deputada") != -1:
            genero = GENERO['feminino']
            self.numero_deputadas += 1
        else:
            genero = GENERO['masculino']

nome_deputadas = NomesDeputadas()
nome_deputadas.main()
