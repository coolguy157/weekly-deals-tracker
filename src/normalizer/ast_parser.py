"""
ast_parser.py
Syntactic parser and linguistic AST distributor for multi-product grocery deals.
Builds typed clause trees and applies Right-Distribution and Left-Distribution transformations.
Replaces character-level sequential regex mutations with a phased Token & AST pipeline.
"""

from typing import List, Optional
import re

from .tokenizer import Token, TokenType, tokenize


class DealASTParser:
    """Parses token streams into AST representation and distributes coordinated expressions."""

    def disaggregate(self, text: str) -> List[str]:
        """Disaggregate a deal string into discrete item names via AST parsing."""
        if not text or not text.strip():
            return []

        tokens = tokenize(text)
        if not tokens:
            return [text]

        # Segment into independent product clauses
        product_token_groups = self.segment_into_products(tokens)
        sub_items: List[str] = []

        for group in product_token_groups:
            expanded = self._parse_single_clause(group)
            sub_items.extend(expanded)

        return sub_items

    def segment_into_products(self, tokens: List[Token]) -> List[List[Token]]:
        """Segment token stream into independent products around bundle boundaries."""
        products = []
        cur_product = []
        head_indices = [i for i, t in enumerate(tokens) if t.type == TokenType.HEAD_NOUN]
        last_boundary_idx = -1

        for i, t in enumerate(tokens):
            is_boundary = False
            if t.type in (TokenType.COMMA, TokenType.COORD):
                has_head_before = any(last_boundary_idx < hi < i for hi in head_indices)
                has_head_after = any(hi > i for hi in head_indices)
                # A boundary exists if there are independent head nouns on both sides
                # OR if there is a unit spec before this comma/coord and another product follows
                has_unit_before = any(last_boundary_idx < ui < i for ui, ut in enumerate(tokens) if ut.type == TokenType.UNIT_SPEC)
                has_brand_after = any(bi > i for bi, bt in enumerate(tokens) if bt.type == TokenType.BRAND)
                if (has_head_before and has_head_after) or (has_unit_before and (has_head_after or has_brand_after)):
                    is_boundary = True

            if is_boundary:
                if cur_product:
                    products.append(cur_product)
                    cur_product = []
                last_boundary_idx = i
            else:
                cur_product.append(t)

        if cur_product:
            products.append(cur_product)

        return products

    def _parse_single_clause(self, tokens: List[Token]) -> List[str]:
        """Parse a single clause into discrete expanded items using AST pattern matching."""
        if not tokens:
            return []

        clause_str = " ".join(t.value for t in tokens)

        # 1. Brand Pair with Shared Size: [BRAND] ,|or [BRAND] [UNIT_SPEC]
        brand_pair = self._match_brand_pair_with_size(tokens)
        if brand_pair:
            return brand_pair

        # 2. Left-Distribution: Brand1 (, Brand2)* or Brand3 + HeadNoun + Size?
        left_dist = self._match_left_distribution(tokens)
        if left_dist:
            return left_dist

        # 3. Produce Prefix List: [Prefix] [HEAD_NOUN] [V1, V2 or V3]
        prefix_list = self._match_prefix_list(tokens)
        if prefix_list:
            return prefix_list

        # 4. Right-Distribution: [Prefix*] M1 (, M2)* or M_last [HEAD_NOUN] [SIZE?]
        right_dist = self._match_right_distribution(tokens)
        if right_dist:
            return right_dist

        return [clause_str]

    def _match_brand_pair_with_size(self, tokens: List[Token]) -> Optional[List[str]]:
        if (
            len(tokens) == 4
            and tokens[0].type == TokenType.BRAND
            and tokens[1].type in (TokenType.COMMA, TokenType.COORD)
            and tokens[2].type == TokenType.BRAND
            and tokens[3].type == TokenType.UNIT_SPEC
        ):
            b1 = tokens[0].value
            b2 = tokens[2].value
            u = tokens[3].value
            return [f"{b1} {u}", f"{b2} {u}"]
        return None

    def _match_left_distribution(self, tokens: List[Token]) -> Optional[List[str]]:
        hn_idx = -1
        for i, t in enumerate(tokens):
            if t.type == TokenType.HEAD_NOUN:
                hn_idx = i
                break

        if hn_idx < 1:
            return None

        pre_tokens = tokens[:hn_idx]
        brand_indices = [i for i, t in enumerate(pre_tokens) if t.type == TokenType.BRAND]
        if len(brand_indices) < 2:
            return None

        # Guard: brands cannot contain unit specs
        if any(t.type == TokenType.UNIT_SPEC for t in pre_tokens):
            return None

        has_coord = any(t.type == TokenType.COORD for t in pre_tokens)
        if not has_coord:
            return None

        head_tokens = [tokens[hn_idx].value]
        trailing_size = " ".join(t.value for t in tokens[hn_idx + 1:] if t.type == TokenType.UNIT_SPEC)
        head_str = " ".join(head_tokens)
        s_str = f" {trailing_size}" if trailing_size else ""

        brands = []
        cur_brand = []
        for t in pre_tokens:
            if t.type in (TokenType.COORD, TokenType.COMMA):
                if cur_brand:
                    brands.append(" ".join(cur_brand))
                    cur_brand = []
            elif t.type == TokenType.BRAND and cur_brand and any(x in ["Greenhouse", "Grown"] for x in cur_brand):
                brands.append(" ".join(cur_brand))
                cur_brand = [t.value]
            else:
                cur_brand.append(t.value)
        if cur_brand:
            brands.append(" ".join(cur_brand))

        if len(brands) >= 2:
            return [f"{b} {head_str}{s_str}" for b in brands]

        return None

    def _match_prefix_list(self, tokens: List[Token]) -> Optional[List[str]]:
        hn_idx = next((i for i, t in enumerate(tokens) if t.type == TokenType.HEAD_NOUN), -1)
        if hn_idx >= 0 and hn_idx < len(tokens) - 2:
            after_tokens = tokens[hn_idx + 1:]
            has_coord = any(t.type == TokenType.COORD for t in after_tokens)
            if has_coord and all(t.type in (TokenType.WORD, TokenType.COMMA, TokenType.COORD) for t in after_tokens):
                prefix_str = " ".join(t.value for t in tokens[:hn_idx + 1])
                vars_list = []
                cur = []
                for t in after_tokens:
                    if t.type in (TokenType.COMMA, TokenType.COORD):
                        if cur:
                            vars_list.append(" ".join(cur))
                            cur = []
                    else:
                        cur.append(t.value)
                if cur:
                    vars_list.append(" ".join(cur))
                if len(vars_list) >= 2:
                    return [f"{prefix_str} {v}" for v in vars_list]
        return None

    def _match_right_distribution(self, tokens: List[Token]) -> Optional[List[str]]:
        hn_idx = -1
        for i, t in enumerate(tokens):
            if t.type == TokenType.HEAD_NOUN:
                hn_idx = i
                break

        if hn_idx < 1:
            return None

        coord_idx = -1
        for i in range(hn_idx - 1, -1, -1):
            if tokens[i].type == TokenType.COORD:
                coord_idx = i
                break

        if coord_idx == -1:
            return None

        mod_tokens = tokens[:hn_idx]
        start_idx = 1 if mod_tokens[0].type == TokenType.BRAND else 0

        # Guard: modifiers cannot contain other head nouns, unit specs, or brands!
        if any(t.type in (TokenType.HEAD_NOUN, TokenType.UNIT_SPEC, TokenType.BRAND) for t in mod_tokens[start_idx:]):
            return None

        suffix_str = " ".join(t.value for t in tokens[hn_idx + 1:])
        s_str = f" {suffix_str}" if suffix_str else ""
        head_str = tokens[hn_idx].value

        prefix_tokens = [mod_tokens[0].value] if start_idx == 1 else []
        prefix_str = (" ".join(prefix_tokens) + " ") if prefix_tokens else ""

        modifiers = []
        cur_mod = []
        for t in mod_tokens[start_idx:]:
            if t.type in (TokenType.COMMA, TokenType.COORD):
                if cur_mod:
                    modifiers.append(" ".join(cur_mod))
                    cur_mod = []
            else:
                cur_mod.append(t.value)
        if cur_mod:
            modifiers.append(" ".join(cur_mod))

        if len(modifiers) >= 2:
            return [f"{prefix_str}{m} {head_str}{s_str}" for m in modifiers]

        return None
