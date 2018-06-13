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

arqs = listdir(DIRETORIO)
saida = open(ARQUIVO_SAIDA, "w")
cont = 0

for arq in arqs:
        ponteiro = open(DIRETORIO+"/"+ arq)
        data = ponteiro.read()
        dom = parseString(data)
        records = dom.getElementsByTagName(TAGS['data'])

        for record in records:
            dep = record.getElementsByTagName(TAGS['mandato'])[0].firstChild.data
            if dep.find("Deputada") != -1:
                genero = GENERO['feminino']
                cont += 1
            else:
                genero = GENERO['masculino']
            nome = record.getElementsByTagName(TAGS['nome_txt'])[0].firstChild.data
            legis = record.getElementsByTagName(
                TAGS['mandato'])[0].firstChild.data
            legis = legis.split(";")
            saida_legis = ""
            for leg in legis:
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

print(cont)
