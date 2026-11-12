"""Testes do painel. Rodar com: python3 -m unittest discover -s tests"""
import datetime as dt
import json
import unittest

from painel import dados as d
from painel import regras, tce_mg


class Formatacao(unittest.TestCase):
    def test_norm_remove_acentos_e_caixa(self):
        self.assertEqual(d.norm("  Até o  Bimestre (c) "), "ATE O BIMESTRE (C)")

    def test_brl(self):
        self.assertEqual(regras.brl(1234567.8), "R$ 1.234.567,80")
        self.assertEqual(regras.brl(-10), "-R$ 10,00")
        self.assertEqual(regras.brl(None), "não informado")

    def test_prazos_legais(self):
        self.assertEqual(regras._prazo(2026, 4, 6), dt.date(2026, 9, 30))   # 4º bimestre
        self.assertEqual(regras._prazo(2026, 6, 6), dt.date(2027, 1, 30))   # 6º bimestre
        self.assertEqual(regras._prazo(2026, 2, 3), dt.date(2026, 9, 30))   # 2º quadrimestre


class LeituraTceMg(unittest.TestCase):
    def test_numero_em_formato_brasileiro(self):
        self.assertEqual(tce_mg._numero("1.234,56"), 1234.56)
        self.assertEqual(tce_mg._numero("R$ 10,00"), 10.0)
        self.assertIsNone(tce_mg._numero("12/03/2026"))

    def test_tabela_detecta_separador_e_soma(self):
        bruto = "Órgão;Valor Empenhado\nSaúde;1.000,50\nEducação;2.000,00\n".encode("cp1252")
        t = tce_mg._tabela("x.csv", bruto)
        self.assertEqual(t["separador"], ";")
        self.assertEqual(t["linhas"], 2)
        self.assertEqual(t["colunas"][0]["nome"], "Órgão")
        self.assertEqual(t["colunas"][1]["soma"], 3000.5)


class DadosColetados(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = d.carregar()
        if not cls.base["rreo"]:
            raise unittest.SkipTest("sem dados coletados")
        cls.anos = sorted({a for a, _ in cls.base["rreo"]})[1:]
        cls.serie = d.art167a(cls.base, cls.anos)

    def test_janela_de_12_meses_no_fechamento_iguala_o_acumulado_do_ano(self):
        for p in self.serie:
            if p["bimestre"] != 6:
                continue
            r = self.base["rreo"][(p["ano"], 6)]
            rc = r.v("01", "ReceitasCorrentes", d.REC_REAL) + (r.v("01", "ReceitasCorrentesIntra", d.REC_REAL) or 0)
            self.assertAlmostEqual(p["receita_corrente"], rc, places=1)

    def test_indice_167a_em_faixa_plausivel(self):
        self.assertTrue(self.serie)
        for p in self.serie:
            self.assertTrue(0.5 < p["indice"] < 1.5, p)

    def test_despesa_nao_supera_o_estagio_anterior(self):
        for r in self.base["rreo"].values():
            t = d.execucao(r)["despesa_total"]
            self.assertLessEqual(t["paga"], t["liquidada"] + 1)
            self.assertLessEqual(t["liquidada"], t["empenhada"] + 1)

    def test_achados_tem_situacao_e_fundamento(self):
        achados = regras.apurar(self.base, self.anos, self.serie, dt.date.today(), False)
        self.assertTrue(achados)
        for a in achados:
            self.assertIn(a["situacao"], {"apontamento", "atencao", "regular", "nao_avaliado"})
            self.assertTrue(a["fundamento"] and a["descricao"], a["id"])
        json.dumps(achados)  # precisa ser serializável


if __name__ == "__main__":
    unittest.main()
