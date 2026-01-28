"""
Local AI Chatbot for English Learning
Uses transformers library with a conversational model that runs locally
"""
import os
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime

try:
    from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print("Warning: transformers not available. Install with: pip install transformers torch")

class EnglishLearningChatbot:
    """
    Local AI chatbot focused on teaching English
    Uses a conversational model that runs entirely on local hardware
    """
    
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.pipeline = None
        self.conversation_history: List[Dict[str, str]] = []
        self.model_loaded = False
        
        # System prompt for English learning
        self.system_prompt = """You are a friendly and patient English teacher AI assistant. Your goal is to help users learn English effectively. 

Guidelines:
- Always respond in English (unless the user asks you to explain something in Turkish)
- Be encouraging and supportive
- Explain grammar rules clearly when asked
- Provide examples for better understanding
- Correct mistakes gently and explain why
- Adapt to the user's level (beginner, intermediate, advanced)
- Use simple language for beginners, more complex for advanced learners
- Encourage practice and provide exercises when appropriate
- Be conversational and friendly, not robotic

Remember: You're here to help them learn, not just to answer questions. Make learning fun and engaging!"""
        
        if TRANSFORMERS_AVAILABLE:
            self._load_model()
    
    def _load_model(self):
        """Load a local conversational model"""
        try:
            # Try to use a smaller, faster model that can run locally
            # Using GPT-2 as a fallback, but ideally use a smaller conversational model
            model_name = "gpt2"  # Small and fast, runs locally
            
            # Check if CUDA is available for GPU acceleration
            device = 0 if torch.cuda.is_available() else -1
            
            print(f"Loading chatbot model: {model_name} (device: {'GPU' if device == 0 else 'CPU'})...")
            
            # Load tokenizer and model
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForCausalLM.from_pretrained(model_name)
            
            # Set pad token if not exists
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # Create text generation pipeline
            self.pipeline = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                device=device,
                max_length=512,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                pad_token_id=self.tokenizer.eos_token_id
            )
            
            self.model_loaded = True
            print("✅ Chatbot model loaded successfully!")
            
        except Exception as e:
            print(f"⚠️ Could not load AI model: {e}")
            print("Chatbot will use rule-based responses as fallback")
            self.model_loaded = False
    
    def _generate_with_model(self, prompt: str) -> str:
        """Generate response using the loaded model"""
        if not self.model_loaded or not self.pipeline:
            return self._fallback_response(prompt)
        
        try:
            # Build full prompt with system message and conversation history
            full_prompt = self._build_prompt(prompt)
            
            # Generate response
            outputs = self.pipeline(
                full_prompt,
                max_new_tokens=150,
                num_return_sequences=1,
                truncation=True,
                pad_token_id=self.tokenizer.eos_token_id
            )
            
            # Extract generated text
            generated_text = outputs[0]['generated_text']
            
            # Remove the prompt part to get only the response
            response = generated_text[len(full_prompt):].strip()
            
            # Clean up response
            response = self._clean_response(response)
            
            return response if response else self._fallback_response(prompt)
            
        except Exception as e:
            print(f"Error generating response: {e}")
            return self._fallback_response(prompt)
    
    def _build_prompt(self, user_message: str) -> str:
        """Build prompt with system message and conversation history"""
        prompt_parts = [self.system_prompt]
        
        # Add recent conversation history (last 5 exchanges)
        recent_history = self.conversation_history[-10:]  # Last 10 messages (5 exchanges)
        for msg in recent_history:
            role = "Student" if msg['role'] == 'user' else "Teacher"
            prompt_parts.append(f"{role}: {msg['content']}")
        
        # Add current user message
        prompt_parts.append(f"Student: {user_message}")
        prompt_parts.append("Teacher:")
        
        return "\n".join(prompt_parts)
    
    def _clean_response(self, response: str) -> str:
        """Clean and format the generated response"""
        # Remove any incomplete sentences at the end
        response = response.strip()
        
        # Stop at common conversation endings
        stop_phrases = ["Student:", "Teacher:", "\n\n", "---"]
        for phrase in stop_phrases:
            if phrase in response:
                response = response.split(phrase)[0].strip()
        
        # Ensure response ends properly
        if response and not response[-1] in '.!?':
            # Try to find last sentence
            sentences = re.split(r'[.!?]', response)
            if len(sentences) > 1:
                response = '.'.join(sentences[:-1]) + '.'
            else:
                response = response + '.'
        
        return response.strip()
    
    def _fallback_response(self, user_message: str) -> str:
        """Fallback rule-based responses when AI model is not available"""
        message_lower = user_message.lower().strip()
        
        # Greetings
        if any(word in message_lower for word in ['hello', 'hi', 'hey', 'merhaba', 'selam']):
            return "Hello! I'm your English learning assistant. How can I help you improve your English today? You can ask me about grammar, vocabulary, pronunciation, or practice conversations!"
        
        # Questions about learning
        if any(word in message_lower for word in ['learn', 'study', 'öğren', 'nasıl']):
            return "Great question! Here are some ways to learn English effectively:\n\n1. Practice daily - even 15 minutes helps\n2. Read English texts (books, articles, subtitles)\n3. Listen to English (movies, podcasts, music)\n4. Speak regularly - practice conversations\n5. Learn new words in context\n6. Don't be afraid to make mistakes - they're part of learning!\n\nWhat would you like to focus on today?"
        
        # Grammar questions
        if any(word in message_lower for word in ['grammar', 'tense', 'verb', 'noun', 'dilbilgisi']):
            return "I'd be happy to help with grammar! Could you be more specific? For example:\n- Present tense vs past tense\n- When to use 'a' vs 'an'\n- Irregular verbs\n- Prepositions\n\nWhat grammar topic would you like to learn about?"
        
        # Vocabulary questions
        if any(word in message_lower for word in ['word', 'vocabulary', 'meaning', 'kelime', 'anlam']):
            return "Vocabulary is essential for learning English! Here are some tips:\n\n- Learn words in context (sentences, not alone)\n- Use flashcards to memorize\n- Practice using new words in your own sentences\n- Review regularly\n\nDo you have a specific word you'd like to learn about?"
        
        # Practice requests
        if any(word in message_lower for word in ['practice', 'exercise', 'alıştırma', 'pratik']):
            return "Let's practice! Here's a simple exercise:\n\nTry to describe your day in English. For example:\n\"Today I woke up early. I had breakfast and then I went to work...\"\n\nOr we can practice specific topics like:\n- Talking about hobbies\n- Describing your family\n- Ordering food in a restaurant\n\nWhat would you like to practice?"
        
        # Default response
        return "That's interesting! I'm here to help you learn English. You can:\n\n- Ask me grammar questions\n- Learn new vocabulary\n- Practice conversations\n- Get explanations about English rules\n- Receive encouragement and tips\n\nWhat would you like to work on?"
    
    def chat(self, user_message: str, user_id: Optional[int] = None) -> Dict[str, any]:
        """
        Process user message and generate response
        
        Args:
            user_message: User's message
            user_id: Optional user ID for personalization
        
        Returns:
            Dictionary with response and metadata
        """
        if not user_message or not user_message.strip():
            return {
                'response': "I'm here to help! Please send me a message.",
                'error': None,
                'model_used': 'fallback'
            }
        
        user_message = user_message.strip()
        
        # Add user message to history
        self.conversation_history.append({
            'role': 'user',
            'content': user_message,
            'timestamp': datetime.now().isoformat()
        })
        
        # Generate response
        if self.model_loaded:
            response = self._generate_with_model(user_message)
            model_used = 'ai_model'
        else:
            response = self._fallback_response(user_message)
            model_used = 'fallback'
        
        # Add assistant response to history
        self.conversation_history.append({
            'role': 'assistant',
            'content': response,
            'timestamp': datetime.now().isoformat()
        })
        
        # Keep history manageable (last 20 messages)
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]
        
        return {
            'response': response,
            'error': None,
            'model_used': model_used,
            'timestamp': datetime.now().isoformat()
        }
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
        return {'success': True, 'message': 'Conversation history cleared'}
    
    def get_history(self) -> List[Dict[str, str]]:
        """Get conversation history"""
        return self.conversation_history.copy()

# Global chatbot instance
_chatbot_instance: Optional[EnglishLearningChatbot] = None

def get_chatbot() -> EnglishLearningChatbot:
    """Get or create chatbot instance"""
    global _chatbot_instance
    if _chatbot_instance is None:
        _chatbot_instance = EnglishLearningChatbot()
    return _chatbot_instance
