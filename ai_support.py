"""
AI Support Technician Module
Handles automated message analysis, knowledge base matching, and troubleshooting guidance
"""

import re
import json
import string
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from collections import Counter
import uuid

from models import db, SupportMessage, KnowledgeBase, MessageAnalysis, AutoResponse, TroubleshootingSession

class AISupport:
    """AI Support Technician for automated responses and troubleshooting"""
    
    def __init__(self):
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after',
            'above', 'below', 'between', 'among', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'can', 'i', 'you', 'he', 'she', 'it', 'we',
            'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'her', 'its',
            'our', 'their', 'this', 'that', 'these', 'those'
        }
        
        self.urgency_keywords = {
            'critical': 1.0, 'urgent': 0.9, 'emergency': 1.0, 'broken': 0.8, 'down': 0.7,
            'not working': 0.8, 'error': 0.6, 'problem': 0.5, 'issue': 0.4, 'help': 0.3,
            'asap': 0.9, 'immediately': 0.9, 'now': 0.7, 'quickly': 0.6
        }
        
        self.sentiment_positive = {'good', 'great', 'excellent', 'perfect', 'awesome', 'thanks', 'thank you'}
        self.sentiment_negative = {'bad', 'terrible', 'awful', 'horrible', 'frustrated', 'angry', 'upset'}
    
    def preprocess_text(self, text: str) -> str:
        """Clean and preprocess text for analysis"""
        # Convert to lowercase
        text = text.lower()
        
        # Remove punctuation except for common tech symbols
        text = re.sub(r'[^\w\s@.-]', ' ', text)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text
    
    def extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text"""
        processed_text = self.preprocess_text(text)
        words = processed_text.split()
        
        # Filter out stop words and short words
        keywords = [word for word in words 
                   if word not in self.stop_words and len(word) > 2]
        
        # Count frequency and return most common
        word_counts = Counter(keywords)
        return [word for word, count in word_counts.most_common(10)]
    
    def calculate_urgency_score(self, text: str) -> float:
        """Calculate urgency score based on keywords and patterns"""
        processed_text = self.preprocess_text(text)
        urgency_score = 0.0
        
        for keyword, score in self.urgency_keywords.items():
            if keyword in processed_text:
                urgency_score = max(urgency_score, score)
        
        # Check for multiple exclamation marks
        if '!!!' in text:
            urgency_score = min(urgency_score + 0.2, 1.0)
        elif '!!' in text:
            urgency_score = min(urgency_score + 0.1, 1.0)
        
        # Check for all caps words
        caps_words = len([word for word in text.split() if word.isupper() and len(word) > 2])
        if caps_words > 0:
            urgency_score = min(urgency_score + (caps_words * 0.1), 1.0)
        
        return min(urgency_score, 1.0)
    
    def detect_sentiment(self, text: str) -> str:
        """Detect sentiment of the message"""
        processed_text = self.preprocess_text(text)
        words = set(processed_text.split())
        
        positive_count = len(words.intersection(self.sentiment_positive))
        negative_count = len(words.intersection(self.sentiment_negative))
        
        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        else:
            return 'neutral'
    
    def categorize_message(self, text: str, keywords: List[str]) -> str:
        """Categorize the message based on content"""
        processed_text = self.preprocess_text(text)
        
        # Define category patterns
        categories = {
            'password_reset': ['password', 'reset', 'forgot', 'login', 'access', 'account'],
            'login_issue': ['login', 'sign in', 'authenticate', 'access', 'username'],
            'technical_error': ['error', 'bug', 'crash', 'broken', 'not working', 'issue'],
            'account_management': ['account', 'profile', 'settings', 'update', 'change'],
            'billing': ['billing', 'payment', 'invoice', 'charge', 'subscription', 'cost'],
            'feature_request': ['feature', 'request', 'add', 'new', 'enhancement', 'improve'],
            'general_inquiry': ['how', 'what', 'when', 'where', 'why', 'question', 'help']
        }
        
        category_scores = {}
        for category, category_keywords in categories.items():
            score = 0
            for keyword in category_keywords:
                if keyword in processed_text:
                    score += 1
                if keyword in keywords:
                    score += 2  # Higher weight for extracted keywords
            category_scores[category] = score
        
        # Return category with highest score, or 'general_inquiry' if no matches
        if max(category_scores.values()) > 0:
            return max(category_scores, key=category_scores.get)
        return 'general_inquiry'
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts using simple word overlap"""
        words1 = set(self.preprocess_text(text1).split())
        words2 = set(self.preprocess_text(text2).split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def find_best_knowledge_match(self, message_text: str, keywords: List[str], category: str) -> Tuple[Optional[KnowledgeBase], float]:
        """Find the best matching knowledge base entry"""
        # Get active knowledge base entries for the category
        knowledge_entries = KnowledgeBase.query.filter_by(
            category=category, 
            is_active=True
        ).all()
        
        if not knowledge_entries:
            # Try to find matches in other categories
            knowledge_entries = KnowledgeBase.query.filter_by(is_active=True).all()
        
        best_match = None
        best_score = 0.0
        
        for entry in knowledge_entries:
            # Calculate similarity with question pattern
            pattern_similarity = self.calculate_similarity(message_text, entry.question_pattern)
            
            # Calculate keyword overlap
            entry_keywords = [kw.strip().lower() for kw in (entry.keywords or '').split(',') if kw.strip()]
            keyword_overlap = len(set(keywords).intersection(set(entry_keywords))) / max(len(keywords), 1)
            
            # Combined score
            combined_score = (pattern_similarity * 0.7) + (keyword_overlap * 0.3)
            
            if combined_score > best_score and combined_score >= entry.confidence_threshold:
                best_match = entry
                best_score = combined_score
        
        return best_match, best_score
    
    def analyze_message(self, message: SupportMessage) -> MessageAnalysis:
        """Analyze a support message and create analysis record"""
        # Extract information from message
        processed_question = self.preprocess_text(message.message_text)
        keywords = self.extract_keywords(message.message_text)
        category = self.categorize_message(message.message_text, keywords)
        sentiment = self.detect_sentiment(message.message_text)
        urgency_score = self.calculate_urgency_score(message.message_text)
        
        # Find best knowledge match
        best_match, confidence_score = self.find_best_knowledge_match(
            message.message_text, keywords, category
        )
        
        # Create analysis record
        analysis = MessageAnalysis(
            message_id=message.id,
            processed_question=processed_question,
            extracted_keywords=','.join(keywords),
            category=category,
            sentiment=sentiment,
            urgency_score=urgency_score,
            matched_knowledge_id=best_match.id if best_match else None,
            confidence_score=confidence_score
        )
        
        db.session.add(analysis)
        db.session.commit()
        
        return analysis
    
    def analyze_text_for_message(self, message: SupportMessage, text: str) -> MessageAnalysis:
        """Analyze arbitrary text for a given message context and create analysis record"""
        processed_question = self.preprocess_text(text)
        keywords = self.extract_keywords(text)
        category = self.categorize_message(text, keywords)
        sentiment = self.detect_sentiment(text)
        urgency_score = self.calculate_urgency_score(text)
        
        # Find best knowledge match for provided text
        best_match, confidence_score = self.find_best_knowledge_match(
            text, keywords, category
        )
        
        analysis = MessageAnalysis(
            message_id=message.id,
            processed_question=processed_question,
            extracted_keywords=','.join(keywords),
            category=category,
            sentiment=sentiment,
            urgency_score=urgency_score,
            matched_knowledge_id=best_match.id if best_match else None,
            confidence_score=confidence_score
        )
        
        db.session.add(analysis)
        db.session.commit()
        
        return analysis
    
    def generate_auto_response(self, message: SupportMessage, analysis: MessageAnalysis) -> Optional[AutoResponse]:
        """Generate an automated response if confidence is high enough"""
        if not analysis.matched_knowledge_id or analysis.confidence_score < 0.6:
            return None
        
        knowledge_entry = KnowledgeBase.query.get(analysis.matched_knowledge_id)
        if not knowledge_entry:
            return None
        
        # Generate response text
        response_text = f"Hi! I found a solution that might help:\n\n{knowledge_entry.solution_text}"
        
        # Add troubleshooting steps if available
        if knowledge_entry.troubleshooting_steps:
            try:
                steps = json.loads(knowledge_entry.troubleshooting_steps)
                if steps:
                    response_text += "\n\n📋 **Troubleshooting Steps:**\n"
                    for i, step in enumerate(steps, 1):
                        response_text += f"{i}. {step}\n"
            except json.JSONDecodeError:
                pass
        
        response_text += "\n\nIf this doesn't solve your issue, a human technician will assist you shortly. You can also provide feedback by replying with 👍 (helpful) or 👎 (not helpful)."
        
        # Create auto response record
        auto_response = AutoResponse(
            message_id=message.id,
            knowledge_base_id=knowledge_entry.id,
            response_text=response_text,
            confidence_score=analysis.confidence_score,
            response_time_seconds=0.5  # Simulated response time
        )
        
        # Update knowledge base usage
        knowledge_entry.usage_count += 1
        
        db.session.add(auto_response)
        db.session.commit()
        
        return auto_response
    
    def start_troubleshooting_session(self, user_telegram_id: str, knowledge_base_id: int) -> Optional[TroubleshootingSession]:
        """Start an interactive troubleshooting session"""
        knowledge_entry = KnowledgeBase.query.get(knowledge_base_id)
        if not knowledge_entry or not knowledge_entry.troubleshooting_steps:
            return None
        
        try:
            steps = json.loads(knowledge_entry.troubleshooting_steps)
            if not steps:
                return None
        except json.JSONDecodeError:
            return None
        
        # Create session
        session = TroubleshootingSession(
            user_telegram_id=user_telegram_id,
            knowledge_base_id=knowledge_base_id,
            session_token=str(uuid.uuid4()),
            total_steps=len(steps),
            session_data=json.dumps({'steps': steps, 'current_responses': []})
        )
        
        db.session.add(session)
        db.session.commit()
        
        return session
    
    def process_troubleshooting_response(self, session: TroubleshootingSession, user_response: str) -> Dict:
        """Process user response in troubleshooting session"""
        try:
            session_data = json.loads(session.session_data)
            steps = session_data['steps']
            responses = session_data.get('current_responses', [])
            
            # Add user response
            responses.append({
                'step': session.current_step,
                'response': user_response,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Move to next step
            session.current_step += 1
            session.last_activity = datetime.utcnow()
            
            # Update session data
            session_data['current_responses'] = responses
            session.session_data = json.dumps(session_data)
            session.user_responses = json.dumps(responses)
            
            # Check if session is complete
            if session.current_step >= session.total_steps:
                session.status = 'completed'
                session.completed_at = datetime.utcnow()
                
                db.session.commit()
                return {
                    'status': 'completed',
                    'message': 'Troubleshooting session completed! If you still need help, a human technician will assist you.'
                }
            
            # Get next step
            next_step = steps[session.current_step]
            db.session.commit()
            
            return {
                'status': 'continue',
                'step': session.current_step + 1,
                'total_steps': session.total_steps,
                'message': next_step
            }
            
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            session.status = 'error'
            db.session.commit()
            return {
                'status': 'error',
                'message': 'An error occurred in the troubleshooting session. A human technician will assist you.'
            }
    
    def update_feedback(self, auto_response_id: int, was_helpful: bool):
        """Update feedback for an auto response"""
        auto_response = AutoResponse.query.get(auto_response_id)
        if auto_response:
            auto_response.was_helpful = was_helpful
            
            # Update knowledge base success rate
            knowledge_entry = auto_response.knowledge_base
            if knowledge_entry:
                # Calculate new success rate
                total_responses = AutoResponse.query.filter_by(
                    knowledge_base_id=knowledge_entry.id
                ).filter(AutoResponse.was_helpful.isnot(None)).count()
                
                helpful_responses = AutoResponse.query.filter_by(
                    knowledge_base_id=knowledge_entry.id,
                    was_helpful=True
                ).count()
                
                if total_responses > 0:
                    knowledge_entry.success_rate = helpful_responses / total_responses
            
            db.session.commit()

# Global AI support instance
ai_support = AISupport()
