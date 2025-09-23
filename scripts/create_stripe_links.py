#!/usr/bin/env python3
"""
Stripe Payment Links Auto-Generation Script
365bot プロジェクト用 - Stripe決済リンク自動生成
"""

import os
import sys
import json
import logging
import stripe
import requests
from datetime import datetime
from typing import Dict, List, Optional

# ログ設定
def setup_logging():
    """ログ設定を初期化"""
    os.makedirs('logs', exist_ok=True)
    log_filename = f"logs/stripe_links_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

class StripePaymentLinkManager:
    def __init__(self):
        """Stripe決済リンク管理クラスの初期化"""
        self.logger = setup_logging()
        self.stripe_secret_key = os.getenv('STRIPE_SECRET_KEY')
        self.aga_price = int(os.getenv('AGA_PRICE', '1480'))
        self.consult_price = int(os.getenv('CONSULT_PRICE', '3000'))
        self.product_type = os.getenv('PRODUCT_TYPE', 'all')
        
        if not self.stripe_secret_key:
            self.logger.error("STRIPE_SECRET_KEY が設定されていません")
            raise ValueError("STRIPE_SECRET_KEY is required")
        
        stripe.api_key = self.stripe_secret_key
        self.logger.info("Stripe API キーを設定しました")
    
    def create_or_get_product(self, name: str, description: str) -> str:
        """Stripe商品を作成または取得"""
        try:
            # 既存商品を検索
            products = stripe.Product.list(limit=100)
            for product in products.data:
                if product.name == name:
                    self.logger.info(f"既存商品を見つけました: {name} (ID: {product.id})")
                    return product.id
            
            # 新規商品作成
            product = stripe.Product.create(
                name=name,
                description=description,
                type='service'
            )
            self.logger.info(f"新規商品を作成しました: {name} (ID: {product.id})")
            return product.id
            
        except Exception as e:
            self.logger.error(f"商品作成エラー: {e}")
            raise
    
    def create_or_get_price(self, product_id: str, amount: int, currency: str = 'jpy') -> str:
        """Stripe価格を作成または取得"""
        try:
            # 既存価格を検索
            prices = stripe.Price.list(product=product_id, limit=100)
            for price in prices.data:
                if price.unit_amount == amount and price.currency == currency:
                    self.logger.info(f"既存価格を見つけました: {amount}{currency.upper()} (ID: {price.id})")
                    return price.id
            
            # 新規価格作成
            price = stripe.Price.create(
                product=product_id,
                unit_amount=amount,
                currency=currency
            )
            self.logger.info(f"新規価格を作成しました: {amount}{currency.upper()} (ID: {price.id})")
            return price.id
            
        except Exception as e:
            self.logger.error(f"価格作成エラー: {e}")
            raise
    
    def create_payment_link(self, price_id: str, product_name: str) -> str:
        """決済リンクを作成"""
        try:
            payment_link = stripe.PaymentLink.create(
                line_items=[{
                    'price': price_id,
                    'quantity': 1
                }],
                after_completion={
                    'type': 'redirect',
                    'redirect': {
                        'url': 'https://example.com/success'
                    }
                },
                allow_promotion_codes=True,
                billing_address_collection='auto',
                metadata={
                    'product_name': product_name,
                    'created_by': '365bot',
                    'created_at': datetime.now().isoformat()
                }
            )
            
            self.logger.info(f"決済リンクを作成しました: {payment_link.url}")
            return payment_link.url
            
        except Exception as e:
            self.logger.error(f"決済リンク作成エラー: {e}")
            raise
    
    def create_aga_guide_link(self) -> str:
        """AGAガイド用決済リンクを作成"""
        self.logger.info(f"AGAガイド決済リンクを作成中... 価格: {self.aga_price}円")
        
        product_id = self.create_or_get_product(
            name="AGA完全ロードマップ PDF",
            description="薄毛改善の完全ガイド。効果的な治療法から日常ケアまで、専門医監修の包括的な内容をPDFでお届けします。"
        )
        
        price_id = self.create_or_get_price(product_id, self.aga_price)
        payment_link = self.create_payment_link(price_id, "AGA完全ロードマップ PDF")
        
        return payment_link
    
    def create_consultation_link(self) -> str:
        """相談デポジット用決済リンクを作成"""
        self.logger.info(f"相談デポジット決済リンクを作成中... 価格: {self.consult_price}円")
        
        product_id = self.create_or_get_product(
            name="専門相談デポジット",
            description="専門カウンセラーとの個別相談セッションのデポジット。ご相談内容に応じて最適なアドバイスを提供いたします。"
        )
        
        price_id = self.create_or_get_price(product_id, self.consult_price)
        payment_link = self.create_payment_link(price_id, "専門相談デポジット")
        
        return payment_link
    
    def save_links_to_file(self, links: Dict[str, str]):
        """決済リンクをファイルに保存"""
        try:
            os.makedirs('output', exist_ok=True)
            filename = f"output/payment_links_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            output_data = {
                'created_at': datetime.now().isoformat(),
                'links': links,
                'prices': {
                    'aga_price': self.aga_price,
                    'consult_price': self.consult_price
                }
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"決済リンクをファイルに保存しました: {filename}")
            
        except Exception as e:
            self.logger.error(f"ファイル保存エラー: {e}")
    
    def run(self):
        """メイン実行処理"""
        self.logger.info("=== Stripe決済リンク自動生成を開始 ===")
        
        try:
            created_links = {}
            
            if self.product_type in ['all', 'aga_guide']:
                aga_link = self.create_aga_guide_link()
                created_links['AGA完全ロードマップ PDF'] = aga_link
            
            if self.product_type in ['all', 'consultation']:
                consult_link = self.create_consultation_link()
                created_links['専門相談デポジット'] = consult_link
            
            # 結果を出力
            self.logger.info("=== 作成された決済リンク ===")
            for product_name, link in created_links.items():
                self.logger.info(f"{product_name}: {link}")
            
            # ファイルに保存
            self.save_links_to_file(created_links)
            
            self.logger.info("=== 処理完了 ===")
            
        except Exception as e:
            self.logger.error(f"処理中にエラーが発生しました: {e}")
            raise

if __name__ == "__main__":
    manager = StripePaymentLinkManager()
    manager.run()
