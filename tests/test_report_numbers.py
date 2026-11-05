"""Synthetic excerpt matching checks; no report or source data is embedded."""
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from weavve.final.report_numbers import compare, report_text, W


HEADERS = ['First order held', 'People', 'Two-year sales per person', 'Index']
ROWS = [HEADERS, ['Bed sheet set only', '2', '$20', '80'],
        ['Duvet insert only', '3', '$30', '120']]
QUOTES = {'Table 11 sheet_set, people': '2', 'Table 11 sheet_set, sales': '$20',
          'Table 11 sheet_set, index': '80', 'Table 11 duvet_insert, index': '120'}


def report(rows):
    text = '\n'.join('\n'.join(row) for row in rows)
    return {'all': text, 'tables': {11: text}, 'table_rows': {11: rows}}


class ReportExcerptTests(unittest.TestCase):
    def test_correct_cells_match(self):
        self.assertEqual(compare(QUOTES, report(ROWS)), {})

    def test_swapped_values_do_not_match_elsewhere_in_table(self):
        rows = [list(row) for row in ROWS]
        rows[1][3], rows[2][3] = rows[2][3], rows[1][3]
        missing = compare(QUOTES, report(rows))
        self.assertEqual(set(missing), {'Table 11 sheet_set, index', 'Table 11 duvet_insert, index'})

    def test_right_value_in_wrong_column_fails(self):
        rows = [list(row) for row in ROWS]
        rows[1][1], rows[1][3] = rows[1][3], rows[1][1]
        missing = compare(QUOTES, report(rows))
        self.assertIn('Table 11 sheet_set, people', missing)
        self.assertIn('Table 11 sheet_set, index', missing)

    def test_column_reordering_follows_headers(self):
        reordered = [[row[i] for i in (3, 0, 2, 1)] for row in ROWS]
        self.assertEqual(compare(QUOTES, report(reordered)), {})

    def test_missing_table_or_structure_fails_closed(self):
        for document in ({'all': '2 $20 80 120', 'tables': {}},
                         {'all': '', 'tables': {11: '2 $20 80 120'}}):
            with self.subTest(document=document):
                self.assertEqual(compare(QUOTES, document), QUOTES)

    def test_duplicate_product_rows_and_headers_fail_closed(self):
        for rows in (ROWS + [ROWS[1]], ROWS + [HEADERS]):
            missing = compare(QUOTES, report(rows))
            self.assertIn('Table 11 sheet_set, people', missing)

    def test_cell_text_must_not_contain_additional_values(self):
        rows = [list(row) for row in ROWS]
        rows[1][3] = '80 or 120'
        self.assertIn('Table 11 sheet_set, index', compare(QUOTES, report(rows)))

    def test_unknown_group_or_metric_fails_closed(self):
        q = {'Table 11 unknown, people': '2', 'Table 11 sheet_set, unrecognized': '80'}
        self.assertEqual(compare(q, report(ROWS)), q)

    def test_nonproduct_excerpts_keep_existing_limited_scope(self):
        q = {'Table 7 sample': '12', 'Section text': 'synthetic phrase'}
        doc = {'all': 'synthetic phrase 12', 'tables': {7: '120'}}
        self.assertEqual(compare(q, doc), {'Table 7 sample': '12'})

    def test_docx_extraction_retains_cells_and_rejects_duplicate_captions(self):
        def add_table(body):
            paragraph = ET.SubElement(body, W + 'p')
            ET.SubElement(ET.SubElement(paragraph, W + 'r'), W + 't').text = 'Table 11. Synthetic fixture'
            table = ET.SubElement(body, W + 'tbl')
            for cells in ROWS:
                row = ET.SubElement(table, W + 'tr')
                for text in cells:
                    cell = ET.SubElement(row, W + 'tc')
                    para = ET.SubElement(cell, W + 'p')
                    ET.SubElement(ET.SubElement(para, W + 'r'), W + 't').text = text

        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'synthetic.docx'
            document = ET.Element(W + 'document')
            body = ET.SubElement(document, W + 'body')
            add_table(body)
            with ZipFile(path, 'w') as z:
                z.writestr('word/document.xml', ET.tostring(document))
            extracted = report_text(path)
            self.assertEqual(extracted['table_rows'][11], ROWS)
            self.assertEqual(compare(QUOTES, extracted), {})
            add_table(body)
            with ZipFile(path, 'w') as z:
                z.writestr('word/document.xml', ET.tostring(document))
            with self.assertRaises(ValueError): report_text(path)


if __name__ == '__main__':
    unittest.main()
