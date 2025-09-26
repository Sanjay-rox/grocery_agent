import os
import json
import asyncio
from typing import Optional, Dict, Any, List
import logging
from groq import Groq
from src.core.config import Config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FreeLLMClient:
    """Free LLM client supporting Groq and Ollama"""
    
    def __init__(self):
        self.groq_client = None
        self.ollama_available = False
        self.request_count = 0
        self.daily_limit = 14400  # Groq free tier limit
        
        # Initialize Groq client
        if Config.GROQ_API_KEY:
            try:
                self.groq_client = Groq(api_key=Config.GROQ_API_KEY)
                logger.info("✅ Groq client initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Groq client: {e}")
        
        # Check Ollama availability
        self.ollama_available = self._check_ollama()
        
        if not self.groq_client and not self.ollama_available:
            logger.warning("⚠️  No LLM services available. Please configure Groq or install Ollama.")
    
    def _check_ollama(self) -> bool:
        """Check if Ollama is available locally"""
        try:
            import ollama
            models = ollama.list()
            if models.get('models'):
                logger.info(f"✅ Ollama available with models: {[m['name'] for m in models['models']]}")
                return True
            else:
                logger.info("ℹ️  Ollama installed but no models found. Run: ollama pull llama3.2:3b")
                return False
        except ImportError:
            logger.info("ℹ️  Ollama not installed. Install with: pip install ollama")
            return False
        except Exception as e:
            logger.error(f"❌ Error checking Ollama: {e}")
            return False
    
    async def get_completion(
        self, 
        prompt: str, 
        system_prompt: str = "",
        use_local: bool = False,
        model: str = None,
        temperature: float = None,
        max_tokens: int = None
    ) -> str:
        """Get completion from available LLM service"""
        
        # Use provided parameters or defaults
        temperature = temperature or Config.TEMPERATURE
        max_tokens = max_tokens or Config.MAX_TOKENS
        model = model or Config.DEFAULT_MODEL
        
        try:
            if use_local and self.ollama_available:
                return await self._get_ollama_completion(prompt, system_prompt, model, temperature)
            elif self.groq_client and self.request_count < self.daily_limit:
                return await self._get_groq_completion(prompt, system_prompt, model, temperature, max_tokens)
            elif self.ollama_available:
                logger.info("🔄 Falling back to Ollama (Groq limit reached or unavailable)")
                return await self._get_ollama_completion(prompt, system_prompt, Config.FALLBACK_MODEL, temperature)
            else:
                raise Exception("No LLM service available")
                
        except Exception as e:
            logger.error(f"❌ LLM completion failed: {e}")
            return f"Error: Unable to process request - {str(e)}"
    
    async def _get_groq_completion(
        self, 
        prompt: str, 
        system_prompt: str, 
        model: str, 
        temperature: float, 
        max_tokens: int
    ) -> str:
        """Get completion from Groq API"""
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            completion = self.groq_client.chat.completions.create(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=1,
                stop=None,
                stream=False
            )
            
            self.request_count += 1
            logger.info(f"✅ Groq completion successful (requests today: {self.request_count})")
            
            return completion.choices[0].message.content
            
        except Exception as e:
            logger.error(f"❌ Groq API error: {e}")
            raise e
    
    async def _get_ollama_completion(
        self, 
        prompt: str, 
        system_prompt: str, 
        model: str, 
        temperature: float
    ) -> str:
        """Get completion from Ollama (local)"""
        
        try:
            import ollama
            
            messages = []
            if system_prompt:
                messages.append({'role': 'system', 'content': system_prompt})
            messages.append({'role': 'user', 'content': prompt})
            
            response = ollama.chat(
                model=model,
                messages=messages,
                options={
                    'temperature': temperature,
                    'num_predict': Config.MAX_TOKENS
                }
            )
            
            logger.info(f"✅ Ollama completion successful with model: {model}")
            return response['message']['content']
            
        except Exception as e:
            logger.error(f"❌ Ollama error: {e}")
            raise e
    
    async def get_json_completion(
        self, 
        prompt: str, 
        system_prompt: str = "",
        schema: Dict = None,
        use_local: bool = False
    ) -> Dict[str, Any]:
        """Get JSON completion with validation"""
        
        # Add JSON instruction to system prompt
        json_instruction = "\n\nIMPORTANT: Respond ONLY with valid JSON. No other text or explanation."
        if schema:
            json_instruction += f"\n\nRequired JSON schema: {json.dumps(schema, indent=2)}"
        
        full_system_prompt = system_prompt + json_instruction
        
        response = await self.get_completion(prompt, full_system_prompt, use_local)
        
        try:
            # Clean response (remove markdown code blocks if present)
            cleaned_response = response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            
            return json.loads(cleaned_response.strip())
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse JSON response: {e}")
            logger.error(f"Raw response: {response}")
            return {"error": "Invalid JSON response", "raw_response": response}
    
    async def get_multiple_completions(
        self, 
        prompts: List[str], 
        system_prompt: str = "",
        use_local: bool = False,
        batch_size: int = 5
    ) -> List[str]:
        """Get multiple completions with rate limiting"""
        
        results = []
        
        # Process in batches to avoid overwhelming the API
        for i in range(0, len(prompts), batch_size):
            batch = prompts[i:i + batch_size]
            
            # Create tasks for concurrent processing
            tasks = [
                self.get_completion(prompt, system_prompt, use_local)
                for prompt in batch
            ]
            
            # Execute batch
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
            
            # Add delay between batches if using external API
            if not use_local and i + batch_size < len(prompts):
                await asyncio.sleep(1)  # 1 second delay
        
        return results
    
    def get_status(self) -> Dict[str, Any]:
        """Get client status information"""
        return {
            "groq_available": self.groq_client is not None,
            "ollama_available": self.ollama_available,
            "request_count": self.request_count,
            "daily_limit": self.daily_limit,
            "requests_remaining": self.daily_limit - self.request_count
        }
    
    def reset_daily_count(self):
        """Reset daily request count (call this daily)"""
        self.request_count = 0
        logger.info("🔄 Daily request count reset")

# Global LLM client instance
llm_client = FreeLLMClient()