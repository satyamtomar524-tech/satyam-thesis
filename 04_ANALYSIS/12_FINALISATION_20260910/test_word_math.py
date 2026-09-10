"""Structural regression checks; rendering is a separate acceptance gate."""
import unittest
from io import BytesIO
from zipfile import ZipFile

from docx import Document
from docx.oxml.ns import qn
from lxml import etree

from word_math import display, fraction, sub, summation, text


class NativeMathTests(unittest.TestCase):
    def test_fraction_has_distinct_arguments(self):
        node = fraction([sub("w", "st"), "+1"], "n")
        self.assertEqual([x.tag for x in node], [qn("m:num"), qn("m:den")])
        self.assertEqual("".join(node[0].itertext()), "wst+1")
        self.assertEqual("".join(node[1].itertext()), "n")

    def test_nodes_are_copied_not_moved(self):
        token = sub("w", "st")
        equation = display(token, "=", fraction(token, "n"))
        self.assertIsNone(token.getparent())
        self.assertEqual(len(equation.findall('.//' + qn('m:sSub'))), 2)

    def test_summation_keeps_body_and_hides_unused_upper_limit(self):
        node = summation("t∈T", sub("w", "st"))
        self.assertEqual(node[0].find(qn("m:supHide")).get(qn("m:val")), "1")
        self.assertEqual("".join(node.find(qn("m:e")).itertext()), "wst")

    def test_native_math_survives_word_package_roundtrip(self):
        doc = Document()
        doc.add_paragraph()._p.append(display(sub("p", "st"), "=", fraction(sub("w", "st"), sub("n", "s"))))
        data = BytesIO()
        doc.save(data)
        data.seek(0)
        xml = etree.fromstring(ZipFile(data).read('word/document.xml'))
        self.assertEqual(len(xml.findall('.//' + qn('m:oMath'))), 1)
        self.assertEqual(len(xml.findall('.//' + qn('m:f'))), 1)
        self.assertNotIn(b'\\frac', etree.tostring(xml))


if __name__ == '__main__':
    unittest.main()
