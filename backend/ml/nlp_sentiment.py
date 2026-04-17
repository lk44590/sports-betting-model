"""
NLP Sentiment Analysis for Sports Betting.
Analyzes news, social media, and injury reports to detect sentiment.
Provides signals for lineup changes, injuries, and momentum shifts.
"""

import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict
import json

# Try to import transformers, use mock if not available
try:
    from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    print("Transformers not available. Using rule-based sentiment analysis.")
    TRANSFORMERS_AVAILABLE = False


@dataclass
class SentimentResult:
    """Result of sentiment analysis."""
    text: str
    sentiment: str  # 'positive', 'negative', 'neutral'
    confidence: float  # 0 to 1
    category: str  # 'injury', 'lineup', 'momentum', 'general'
    entities: List[str]  # Player/team names mentioned
    impact_score: float  # -1 to 1, betting impact


class NLPSentimentAnalyzer:
    """
    NLP-based sentiment analyzer for sports betting.
    Uses pre-trained models or rule-based fallback.
    """
    
    def __init__(self):
        self.sentiment_pipeline = None
        self.ner_pipeline = None
        
        # Initialize models if available
        if TRANSFORMERS_AVAILABLE:
            try:
                # Load lightweight sentiment model
                self.sentiment_pipeline = pipeline(
                    "sentiment-analysis",
                    model="distilbert-base-uncased-finetuned-sst-2-english",
                    truncation=True,
                    max_length=512
                )
                print("Loaded transformer sentiment model")
            except Exception as e:
                print(f"Error loading transformer model: {e}")
                self.sentiment_pipeline = None
        
        # Compile keyword patterns
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns for rule-based analysis."""
        # Injury-related keywords
        self.injury_keywords = {
            'high': [
                'out for season', 'torn acl', 'broken leg', 'season ending',
                'surgery', 'placed on ir', 'injured reserve', 'career threatening'
            ],
            'medium': [
                'questionable', 'doubtful', 'game-time decision', 'day-to-day',
                'hamstring', 'ankle sprain', 'knee injury', 'concussion protocol'
            ],
            'low': [
                'minor injury', 'precautionary', 'rest', 'maintenance',
                'soreness', 'bump', 'bruise'
            ]
        }
        
        # Positive momentum keywords
        self.positive_keywords = [
            'dominant', 'unstoppable', 'hot streak', 'surging', 'momentum',
            'clutch', 'victory', 'champion', 'playoff bound', 'contender'
        ]
        
        # Negative momentum keywords
        self.negative_keywords = [
            'slumping', 'struggling', 'losing streak', 'eliminated', 'injury prone',
            'underperforming', 'disappointing', 'blowout loss', 'rebuilding'
        ]
        
        # Lineup change keywords
        self.lineup_keywords = [
            'starting', 'bench', 'resting', 'sitting out', 'backup',
            'call-up', 'sent down', 'traded', 'acquired', 'waived'
        ]
    
    def analyze_text(self, text: str, context: str = "general") -> SentimentResult:
        """
        Analyze sentiment of a text snippet.
        
        Args:
            text: Text to analyze
            context: Context type ('injury', 'lineup', 'momentum', 'general')
        """
        text_lower = text.lower()
        
        # Extract entities (player/team names)
        entities = self._extract_entities(text)
        
        # Determine category
        category = self._determine_category(text_lower, context)
        
        # Calculate sentiment
        if self.sentiment_pipeline:
            sentiment, confidence = self._transformer_sentiment(text)
        else:
            sentiment, confidence = self._rule_based_sentiment(text_lower, category)
        
        # Calculate impact score
        impact = self._calculate_impact(text_lower, sentiment, category, confidence)
        
        return SentimentResult(
            text=text,
            sentiment=sentiment,
            confidence=confidence,
            category=category,
            entities=entities,
            impact_score=impact
        )
    
    def _transformer_sentiment(self, text: str) -> tuple:
        """Use transformer model for sentiment."""
        try:
            result = self.sentiment_pipeline(text)[0]
            sentiment = result['label'].lower()
            confidence = result['score']
            
            # Normalize sentiment
            if 'positive' in sentiment:
                return 'positive', confidence
            elif 'negative' in sentiment:
                return 'negative', confidence
            else:
                return 'neutral', confidence
        except:
            return 'neutral', 0.5
    
    def _rule_based_sentiment(self, text: str, category: str) -> tuple:
        """Use rule-based sentiment analysis."""
        # Count keyword matches
        pos_count = sum(1 for kw in self.positive_keywords if kw in text)
        neg_count = sum(1 for kw in self.negative_keywords if kw in text)
        
        # Category-specific adjustments
        if category == 'injury':
            # Injuries are generally negative for the team
            injury_score = self._calculate_injury_severity(text)
            if injury_score > 0.5:
                return 'negative', min(0.9, 0.6 + injury_score * 0.3)
        
        elif category == 'lineup':
            # Lineup changes can be positive or negative
            if any(kw in text for kw in ['starting', 'returning', 'activating']):
                return 'positive', 0.7
            elif any(kw in text for kw in ['sitting out', 'resting', 'injury']):
                return 'negative', 0.6
        
        # General sentiment
        if pos_count > neg_count:
            confidence = min(0.9, 0.5 + (pos_count - neg_count) * 0.1)
            return 'positive', confidence
        elif neg_count > pos_count:
            confidence = min(0.9, 0.5 + (neg_count - pos_count) * 0.1)
            return 'negative', confidence
        else:
            return 'neutral', 0.5
    
    def _calculate_injury_severity(self, text: str) -> float:
        """Calculate injury severity score."""
        severity = 0.0
        
        for keyword in self.injury_keywords['high']:
            if keyword in text:
                severity = max(severity, 1.0)
        
        for keyword in self.injury_keywords['medium']:
            if keyword in text:
                severity = max(severity, 0.6)
        
        for keyword in self.injury_keywords['low']:
            if keyword in text:
                severity = max(severity, 0.3)
        
        return severity
    
    def _determine_category(self, text: str, context: str) -> str:
        """Determine the category of news."""
        # Check for injury-related terms
        injury_terms = ['injury', 'injured', 'hurt', 'out', 'questionable', 'doubtful']
        if any(term in text for term in injury_terms):
            return 'injury'
        
        # Check for lineup terms
        lineup_terms = ['starting', 'bench', 'rotation', 'minutes', 'rest']
        if any(term in text for term in lineup_terms):
            return 'lineup'
        
        # Check for momentum terms
        momentum_terms = ['streak', 'momentum', 'hot', 'cold', 'surging', 'slumping']
        if any(term in text for term in momentum_terms):
            return 'momentum'
        
        return context if context else 'general'
    
    def _extract_entities(self, text: str) -> List[str]:
        """Extract player and team names from text."""
        entities = []
        
        # Simple regex-based extraction
        # Capitalized words (potential names)
        name_pattern = r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b'
        potential_names = re.findall(name_pattern, text)
        
        # Filter out common false positives
        false_positives = {'The', 'A', 'An', 'This', 'That', 'NBA', 'NFL', 'NHL', 'MLB'}
        entities = [name for name in potential_names if name not in false_positives]
        
        return list(set(entities))[:5]  # Top 5 unique entities
    
    def _calculate_impact(self, text: str, sentiment: str, category: str, confidence: float) -> float:
        """
        Calculate betting impact score (-1 to 1).
        Higher absolute value = more significant for betting.
        """
        base_impact = 0.0
        
        # Sentiment direction
        if sentiment == 'positive':
            base_impact = 0.3
        elif sentiment == 'negative':
            base_impact = -0.3
        
        # Category multipliers
        multipliers = {
            'injury': 1.5,
            'lineup': 1.2,
            'momentum': 0.8,
            'general': 0.5
        }
        
        multiplier = multipliers.get(category, 0.5)
        
        # Adjust for confidence
        impact = base_impact * multiplier * confidence
        
        # Cap at -1 to 1
        return max(-1.0, min(1.0, impact))
    
    def analyze_news_batch(self, news_items: List[Dict[str, Any]]) -> List[SentimentResult]:
        """Analyze a batch of news items."""
        results = []
        for item in news_items:
            text = item.get('text', item.get('title', ''))
            context = item.get('category', 'general')
            result = self.analyze_text(text, context)
            results.append(result)
        return results
    
    def get_team_sentiment_summary(self, team_name: str, news_items: List[Dict]) -> Dict[str, Any]:
        """
        Generate sentiment summary for a team based on recent news.
        """
        relevant_news = [
            item for item in news_items
            if team_name.lower() in item.get('text', '').lower() or
               team_name.lower() in item.get('title', '').lower()
        ]
        
        if not relevant_news:
            return {
                'team': team_name,
                'news_count': 0,
                'overall_sentiment': 'neutral',
                'impact_score': 0.0,
                'key_concerns': []
            }
        
        # Analyze all relevant news
        analyzed = self.analyze_news_batch(relevant_news)
        
        # Calculate aggregates
        sentiment_counts = defaultdict(int)
        total_impact = 0
        concerns = []
        
        for result in analyzed:
            sentiment_counts[result.sentiment] += 1
            total_impact += result.impact_score
            
            if result.category == 'injury' and result.impact_score < -0.5:
                concerns.append({
                    'type': 'injury',
                    'text': result.text[:100] + '...' if len(result.text) > 100 else result.text,
                    'impact': result.impact_score
                })
        
        # Determine overall sentiment
        total = len(analyzed)
        if sentiment_counts['positive'] > sentiment_counts['negative']:
            overall = 'positive'
        elif sentiment_counts['negative'] > sentiment_counts['positive']:
            overall = 'negative'
        else:
            overall = 'neutral'
        
        avg_impact = total_impact / total if total > 0 else 0
        
        return {
            'team': team_name,
            'news_count': total,
            'overall_sentiment': overall,
            'sentiment_breakdown': dict(sentiment_counts),
            'impact_score': round(avg_impact, 3),
            'key_concerns': concerns[:3],  # Top 3 concerns
            'sample_news': analyzed[0].text[:200] if analyzed else None
        }
    
    def detect_lineup_changes(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Detect lineup changes from text.
        Returns details if lineup change detected.
        """
        text_lower = text.lower()
        
        # Check for lineup indicators
        lineup_indicators = [
            'starting', 'starting lineup', 'will start', 'getting the start',
            'sitting out', 'resting', ' DNPs', 'inactive', 'out tonight'
        ]
        
        if not any(indicator in text_lower for indicator in lineup_indicators):
            return None
        
        # Extract affected players
        entities = self._extract_entities(text)
        
        # Determine change type
        if any(kw in text_lower for kw in ['sitting', 'rest', 'out', 'inactive']):
            change_type = 'out'
            impact = -0.6
        elif any(kw in text_lower for kw in ['starting', 'will start']):
            change_type = 'in'
            impact = 0.4
        else:
            change_type = 'unclear'
            impact = 0.0
        
        return {
            'detected': True,
            'change_type': change_type,
            'players_affected': entities,
            'impact_score': impact,
            'source_text': text[:200]
        }


# Global instance
sentiment_analyzer = NLPSentimentAnalyzer()


def test_nlp_sentiment():
    """Test the NLP sentiment analyzer."""
    print("Testing NLP Sentiment Analyzer")
    print("=" * 60)
    
    test_cases = [
        {
            'text': 'LeBron James questionable with hamstring injury for tonight\'s game',
            'category': 'injury'
        },
        {
            'text': 'Lakers on a 5-game winning streak, dominating opponents',
            'category': 'momentum'
        },
        {
            'text': 'Stephen Curry cleared to return, will start tonight',
            'category': 'lineup'
        },
        {
            'text': 'Team announces star player out for season with torn ACL',
            'category': 'injury'
        },
        {
            'text': 'Coach says team is focused and ready for the playoffs',
            'category': 'general'
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\nTest {i}:")
        print(f"Text: {test['text']}")
        
        result = sentiment_analyzer.analyze_text(test['text'], test['category'])
        
        print(f"Sentiment: {result.sentiment} (confidence: {result.confidence:.2f})")
        print(f"Category: {result.category}")
        print(f"Impact Score: {result.impact_score:.3f}")
        print(f"Entities: {result.entities}")
    
    # Test team summary
    print("\n" + "=" * 60)
    print("Team Sentiment Summary Test:")
    
    team_news = [
        {'text': 'Lakers lose third straight game, defense struggling'},
        {'text': 'Anthony Davis returns to practice, questionable for Friday'},
        {'text': 'LeBron James scores 40 points in dominant performance'},
        {'text': 'Lakers trade for defensive specialist at deadline'}
    ]
    
    summary = sentiment_analyzer.get_team_sentiment_summary('Lakers', team_news)
    print(f"\nLakers Summary:")
    print(f"  News count: {summary['news_count']}")
    print(f"  Overall sentiment: {summary['overall_sentiment']}")
    print(f"  Impact score: {summary['impact_score']}")
    print(f"  Breakdown: {summary['sentiment_breakdown']}")
    
    # Test lineup detection
    print("\n" + "=" * 60)
    print("Lineup Change Detection Test:")
    
    lineup_text = "Breaking: Kevin Durant will sit out tonight's game for rest"
    lineup_change = sentiment_analyzer.detect_lineup_changes(lineup_text)
    
    if lineup_change:
        print(f"Detected lineup change!")
        print(f"  Type: {lineup_change['change_type']}")
        print(f"  Players: {lineup_change['players_affected']}")
        print(f"  Impact: {lineup_change['impact_score']}")


if __name__ == "__main__":
    test_nlp_sentiment()
