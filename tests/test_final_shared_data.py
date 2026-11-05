"""Synthetic regressions for the legacy analysis adapter over shared tables."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from weavve.final import data


def order(identity, net, discount):
    return {'order_id': identity, 'customer_id': 'synthetic-customer',
            'person_id': 'synthetic-person', 'channel_detail': 'Shopee',
            'original_channels': ['synthetic-marketplace'], 'order_date': date(2031, 2, 3),
            'net': Decimal(net), 'discount': Decimal(discount),
            'is_purchase': Decimal(net) > 0}


def line(identity, net, discount, raw_net, raw_discount, kind='order'):
    return {'order_id': identity, 'net': Decimal(net), 'discount': Decimal(discount),
            'Net sales': Decimal(raw_net), 'Discounts': Decimal(raw_discount),
            'Total sales': Decimal(raw_net), 'Order or sales reversal': kind,
            'Day': date(2031, 2, 4), 'Discount code': 'SYNTHETIC',
            'source_row': 2, 'source_note': 'synthetic provenance'}


class FakeDataset:
    def __init__(self, tables):
        self.tables = tables
        self.calls = []

    def table(self, name):
        self.calls.append(name)
        return self.tables[name]


class FinalSharedDataTests(unittest.TestCase):
    def setUp(self):
        data.order_view.cache_clear()
        data.rows.cache_clear()
        data.search_console.cache_clear()
        self.tables = {
            'orders': [order('purchase', '75', '7.5'), order('zero', '0', '0'),
                       order('negative', '-3', '-1')],
            'order_lines': [line('purchase', '100', '10', '109', '-10.9'),
                            line('purchase', '-25', '-2.5', '-27.25', '2.725', 'reversal'),
                            line('zero', '0', '0', '0', '0'),
                            line('negative', '-3', '-1', '-3.27', '1.09', 'reversal')],
        }
        self.original = deepcopy(self.tables)
        self.dataset = FakeDataset(self.tables)
        self.patcher = patch.object(data, 'dataset', return_value=self.dataset)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        data.order_view.cache_clear()
        data.rows.cache_clear()
        data.search_console.cache_clear()

    def test_canonical_signed_money_is_reused_without_another_tax_adjustment(self):
        result = data.order_view()
        self.assertEqual(len(result), 1)
        purchase = result[0]
        self.assertEqual(purchase['net'], 75.0)
        self.assertEqual(purchase['discount'], 7.5)
        self.assertEqual([r['Net sales'] for r in purchase['rows']], [Decimal('100'), Decimal('-25')])
        self.assertEqual([r['Discounts'] for r in purchase['rows']], [Decimal('-10'), Decimal('2.5')])
        self.assertTrue(purchase['has_negative_discount'])
        self.assertFalse(purchase['cancelled'])

    def test_source_fields_survive_and_adapter_does_not_mutate_shared_tables(self):
        adapted = data.order_view()[0]['rows'][0]
        source = self.original['order_lines'][0]
        for field, value in source.items():
            if field not in {'Net sales', 'Discounts'}:
                with self.subTest(field=field):
                    self.assertEqual(adapted[field], value)
        self.assertEqual(self.tables, self.original)
        self.assertEqual(data.rows('C')[0]['Net sales'], Decimal('109'))
        self.assertEqual(data.rows('C')[0]['net'], Decimal('100'))

    def test_nonpositive_orders_remain_available_for_signed_sales(self):
        result = {r['order']: r for r in data.order_view(positive_only=False)}
        self.assertEqual(set(result), {'purchase', 'zero', 'negative'})
        self.assertEqual(result['zero']['net'], 0.0)
        self.assertEqual(result['negative']['net'], -3.0)
        self.assertEqual(result['negative']['discount'], -1.0)
        self.assertFalse(result['negative']['has_negative_discount'])
        self.assertEqual([r['order'] for r in data.order_view(positive_only=True)], ['purchase'])

    def test_identity_channel_and_order_date_come_from_canonical_order(self):
        result = data.order_view()[0]
        source = self.original['orders'][0]
        self.assertEqual(result['order'], source['order_id'])
        self.assertEqual(result['customer'], source['customer_id'])
        self.assertEqual(result['person'], source['person_id'])
        self.assertEqual(result['channel'], source['channel_detail'])
        self.assertEqual(result['original_channels'], source['original_channels'])
        self.assertEqual(result['date'], source['order_date'])
        self.assertNotEqual(result['date'], result['rows'][0]['Day'])

    def test_raw_inputs_or_alternate_cleaning_modes_are_rejected(self):
        for kwargs in ({'records': ()}, {'drop_cancelled': False}, {'drop_repeated': False}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError): data.order_view(**kwargs)
        # lru_cache rejects an unhashable raw list before the explicit mode guard.
        # Both outcomes fail closed; neither may read or transform supplied raw rows.
        with self.assertRaises((TypeError, ValueError)):
            data.order_view(records=[{'synthetic': 'raw row'}])
        self.assertEqual(self.dataset.calls, [])

    def test_support_aliases_use_the_named_shared_tables(self):
        aliases = {
            ('D', None): 'products',
            ('G', 'Person map'): 'g_person_map',
            ('G', 'Order channel'): 'g_order_channels',
            ('I', None): 'clearance_skus',
            ('E', None): 'discounts',
            ('E', 'Full Discounts Report'): 'discounts',
            ('E', 'Discount Detail by Code'): 'discount_detail_by_code',
            ('E', 'Discount by Year'): 'discount_by_year',
            ('E', 'FirstWelcome Order Discount by '): 'discount_summary',
            ('E', 'Alia by Discount Depth'): 'discount_alia_depth',
            ('F', None): 'loyalty_rewards',
            ('F', 'Redemptions'): 'loyalty_rewards',
            ('J', None): 'subscribers',
            ('J', 'Subscribers'): 'subscribers',
            ('K', None): 'email_campaigns',
            ('12', None): 'ads_keywords',
            ('12', 'Search keyword report All time '): 'ads_keywords',
        }
        for name in set(aliases.values()):
            self.tables[name] = [{'synthetic_table': name, 'original_field': 'preserved'}]
        for (code, sheet), name in aliases.items():
            with self.subTest(code=code, sheet=sheet):
                self.assertEqual(data.rows(code, sheet), self.tables[name])
                self.assertIn(name, self.dataset.calls)

    def test_unknown_support_alias_does_not_fall_back_to_another_table(self):
        with self.assertRaises(ValueError): data.rows('J', 'unknown sheet')
        self.assertEqual(self.dataset.calls, [])

    def test_search_console_preserves_missing_query_metrics_and_country_total(self):
        month = date(2031, 2, 1)
        self.tables['gsc_queries'] = [
            {'month': month, 'query': 'synthetic observed', 'clicks': 4},
            {'month': month, 'query': 'synthetic missing', 'clicks': None},
            {'month': month, 'query': 'synthetic zero', 'clicks': 0},
        ]
        self.tables['gsc_months'] = [
            {'month': month, 'clicks': 17, 'query_click_coverage': None,
             'source_file': 'synthetic/gsc.xlsx'},
        ]
        original = deepcopy(self.tables)

        result = data.search_console()

        self.assertEqual(result, {(2031, 2): {
            'clicks': 17,
            'queries': {'synthetic observed': 4, 'synthetic missing': None,
                        'synthetic zero': 0},
            'query_rows': [{'query': 'synthetic observed', 'clicks': 4},
                           {'query': 'synthetic missing', 'clicks': None},
                           {'query': 'synthetic zero', 'clicks': 0}],
            'query_click_coverage': None,
            'source_file': 'synthetic/gsc.xlsx',
        }})
        self.assertEqual(self.tables, original)
        self.assertEqual(self.dataset.calls, ['gsc_queries', 'gsc_months'])

    def test_search_console_blank_duplicate_never_erases_observed_clicks(self):
        month = date(2031, 2, 1)
        self.tables['gsc_months'] = [
            {'month': month, 'clicks': 17, 'query_click_coverage': None,
             'source_file': 'synthetic/gsc.xlsx'},
        ]
        for observed in (4, 0):
            for clicks in ([observed, None], [None, observed]):
                with self.subTest(clicks=clicks):
                    data.search_console.cache_clear()
                    self.tables['gsc_queries'] = [
                        {'month': month, 'query': 'synthetic duplicate', 'clicks': value}
                        for value in clicks
                    ]
                    original = deepcopy(self.tables)

                    result = data.search_console()[(2031, 2)]

                    self.assertEqual(result['queries'], {'synthetic duplicate': observed})
                    self.assertEqual(len(result['query_rows']), 2)
                    self.assertEqual(result['query_rows'], [
                        {'query': 'synthetic duplicate', 'clicks': value}
                        for value in clicks
                    ])
                    self.assertEqual(result['clicks'], 17)
                    self.assertIsNone(result['query_click_coverage'])
                    self.assertEqual(self.tables, original)

    def test_search_console_rejects_multiple_numeric_rows_for_one_month_query(self):
        month = date(2031, 2, 1)
        self.tables['gsc_months'] = [
            {'month': month, 'clicks': 17, 'query_click_coverage': None,
             'source_file': 'synthetic/gsc.xlsx'},
        ]
        for clicks in ([4, 7], [0, 4], [4, 0], [0, 0], [4, None, 4]):
            with self.subTest(clicks=clicks):
                data.search_console.cache_clear()
                self.tables['gsc_queries'] = [
                    {'month': month, 'query': 'synthetic duplicate', 'clicks': value}
                    for value in clicks
                ]
                original = deepcopy(self.tables)

                with self.assertRaisesRegex(ValueError, 'Multiple observed GSC rows'):
                    data.search_console()

                self.assertEqual(self.tables, original)


if __name__ == '__main__':
    unittest.main()
