"""
Grammar Analyzer Module
Analyzes English sentence structures and provides grammatical explanations
"""
import re
import nltk
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

# Download required NLTK data
def download_nltk_resources():
    """Download required NLTK resources"""
    resources_to_check = [
        ('punkt', 'tokenizers/punkt'),
        ('punkt_tab', 'tokenizers/punkt_tab'),
        ('averaged_perceptron_tagger', 'taggers/averaged_perceptron_tagger'),
        ('averaged_perceptron_tagger_eng', 'taggers/averaged_perceptron_tagger_eng'),
        ('maxent_ne_chunker', 'chunkers/maxent_ne_chunker'),
        ('words', 'corpora/words'),
        ('wordnet', 'corpora/wordnet')
    ]
    
    for resource_name, resource_path in resources_to_check:
        try:
            nltk.data.find(resource_path)
        except LookupError:
            try:
                print(f"📥 Downloading NLTK resource: {resource_name}...")
                nltk.download(resource_name, quiet=True)
                print(f"✅ Downloaded: {resource_name}")
            except Exception as e:
                # Some resources might not be available, continue
                if 'averaged_perceptron_tagger_eng' not in resource_name:
                    print(f"⚠️ Warning: Could not download {resource_name}: {e}")

# Download resources on import
try:
    download_nltk_resources()
except Exception as e:
    print(f"⚠️ Warning: Error downloading NLTK resources: {e}")

from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.tag import pos_tag
from nltk.chunk import ne_chunk
from nltk.tree import Tree


class GrammarAnalyzer:
    """Analyzes English sentence structures and provides grammatical explanations"""
    
    # POS tag explanations in Turkish
    POS_EXPLANATIONS = {
        'NN': 'İsim (tekil)',
        'NNS': 'İsim (çoğul)',
        'NNP': 'Özel isim (tekil)',
        'NNPS': 'Özel isim (çoğul)',
        'PRP': 'Kişi zamiri (I, you, he, she)',
        'PRP$': 'İyelik zamiri (my, your, his)',
        'DT': 'Belirteç (the, a, an)',
        'VB': 'Fiil (temel form)',
        'VBD': 'Fiil (geçmiş zaman)',
        'VBG': 'Fiil (şimdiki zaman -ing)',
        'VBN': 'Fiil (geçmiş zaman ortacı)',
        'VBP': 'Fiil (geniş zaman, tekil olmayan)',
        'VBZ': 'Fiil (geniş zaman, 3. tekil şahıs)',
        'JJ': 'Sıfat',
        'JJR': 'Sıfat (karşılaştırmalı)',
        'JJS': 'Sıfat (üstünlük)',
        'RB': 'Zarf',
        'RBR': 'Zarf (karşılaştırmalı)',
        'RBS': 'Zarf (üstünlük)',
        'IN': 'Edat (in, on, at, with)',
        'CC': 'Bağlaç (and, but, or)',
        'CD': 'Sayı',
        'TO': 'To (mastar)',
        'MD': 'Yardımcı fiil (can, will, should)',
        'WDT': 'Soru kelimesi (which, what)',
        'WP': 'Soru zamiri (who, what)',
        'WRB': 'Soru zarfı (where, when, why)',
        'EX': 'Varoluşsal there',
        'UH': 'Ünlem',
        'POS': 'İyelik işareti (\'s)',
        'RP': 'Parçacık (up, down, out)',
    }
    
    # Sentence structure patterns with detailed educational explanations
    STRUCTURE_PATTERNS = {
        'simple': {
            'pattern': r'^(PRP|NN|NNP|DT\s+NN).*VB.*$',
            'explanation': 'Basit Cümle (Simple Sentence)',
            'detailed': 'Bu cümle yapısı bir özne ve bir fiil içerir. En temel İngilizce cümle yapısıdır.',
            'structure': 'Özne (Subject) + Fiil (Verb) + [Nesne (Object)]',
            'examples': ['I work.', 'She loves music.', 'They play football.'],
            'tips': 'Basit cümleler net ve anlaşılır mesajlar iletir. Günlük konuşmada en sık kullanılan yapıdır.',
            'translation_tip': 'Türkçe\'de de benzer yapı: "Ben çalışıyorum" gibi.'
        },
        'compound': {
            'pattern': r'.*CC.*',
            'explanation': 'Birleşik Cümle (Compound Sentence)',
            'detailed': 'İki bağımsız cümle "and", "but", "or", "so" gibi bağlaçlarla birleştirilmiştir.',
            'structure': 'Cümle 1 + Bağlaç (and/but/or/so) + Cümle 2',
            'examples': ['I like coffee, and she likes tea.', 'He tried hard, but he failed.', 'You can stay, or you can leave.'],
            'tips': 'Bağlaçlar iki fikir arasındaki ilişkiyi gösterir: "and" (ve/ekleme), "but" (ama/zıtlık), "or" (veya/seçenek).',
            'translation_tip': 'Türkçe\'de: "Kahve severim ve çay da içerim" gibi.'
        },
        'complex': {
            'pattern': r'.*(WDT|WP|WRB|IN).*',
            'explanation': 'Karmaşık Cümle (Complex Sentence)',
            'detailed': 'Ana cümle (independent clause) ve yan cümle (dependent clause) içerir. Yan cümle bağlaç veya zamir ile başlar.',
            'structure': 'Ana Cümle + [Bağlaç/Zamir] + Yan Cümle',
            'examples': ['I know that you are right.', 'When it rains, I stay home.', 'She is happy because she passed.'],
            'tips': 'Yan cümle tek başına anlamlı değildir, ana cümleye bağlıdır. "that", "when", "because", "if" gibi kelimelerle başlar.',
            'translation_tip': 'Türkçe\'de: "Yağmur yağdığında evde kalırım" gibi.'
        },
        'passive': {
            'pattern': r'.*VBN.*(by|BY).*',
            'explanation': 'Edilgen Çatı (Passive Voice)',
            'detailed': 'Özne işi yapan değil, işten etkilenendir. Vurgu eyleme değil, eylemden etkilenene yapılır.',
            'structure': 'Özne + am/is/are/was/were + V3 (Past Participle) + [by + Fail]',
            'examples': ['The book was written by him.', 'English is spoken worldwide.', 'The car was repaired yesterday.'],
            'tips': 'Edilgen çatı, işi yapanın önemli olmadığında veya bilinmediğinde kullanılır. "by" ile işi yapan belirtilir.',
            'translation_tip': 'Türkçe\'de: "Kitap onun tarafından yazıldı" gibi. "-ıl, -il" ekleri İngilizce\'deki edilgen çatıya benzer.'
        },
        'question': {
            'pattern': r'^(WDT|WP|WRB|MD|VBZ|VBD|DO|DOES|DID).*',
            'explanation': 'Soru Cümlesi (Question)',
            'detailed': 'Bilgi almak için kullanılan cümle yapısı. Soru kelimesi veya yardımcı fiil ile başlar.',
            'structure': 'Soru Kelimesi/Yardımcı Fiil + Özne + Fiil + [Nesne] + ?',
            'examples': ['What are you doing?', 'Do you like coffee?', 'Where did you go?', 'Can you help me?'],
            'tips': 'Yes/No soruları yardımcı fiille başlar (Do, Does, Did, Can, Will). Bilgi soruları soru kelimesiyle başlar (What, Where, When, Why, How).',
            'translation_tip': 'Türkçe\'de soru eki "mı, mi, mu, mü" kullanılır, İngilizce\'de kelime sırası değişir.'
        },
        'imperative': {
            'pattern': r'^(VB|VBG).*',
            'explanation': 'Emir Cümlesi (Imperative)',
            'detailed': 'Özne olmadan doğrudan fiil ile başlayan, emir, rica veya talimat veren cümle.',
            'structure': 'Fiil (Verb) + [Nesne] + [Lütfen/Please]',
            'examples': ['Close the door.', 'Please help me.', 'Don\'t worry.', 'Be careful!'],
            'tips': 'Emir cümleleri genellikle özne kullanmaz (gizli "you" vardır). Olumsuz emirlerde "Don\'t" kullanılır.',
            'translation_tip': 'Türkçe\'de: "Kapıyı kapat", "Lütfen yardım et" gibi.'
        },
        'conditional': {
            'pattern': r'.*(if|IF|unless|UNLESS).*',
            'explanation': 'Koşul Cümlesi (Conditional)',
            'detailed': '"if" veya "unless" ile başlayan koşullu yapı. Bir durumun gerçekleşmesi için başka bir durumun gerekli olduğunu gösterir.',
            'structure': 'If + Koşul + Sonuç / Sonuç + if + Koşul',
            'examples': ['If it rains, I will stay home.', 'I will help you if you ask.', 'Unless you study, you will fail.'],
            'tips': '"If" = eğer, "unless" = -medikçe/-madıkça anlamındadır. Koşul cümlesi gelecek, şimdiki veya geçmiş zaman olabilir.',
            'translation_tip': 'Türkçe\'de: "Eğer yağmur yağarsa, evde kalacağım" gibi.'
        },
        'relative': {
            'pattern': r'.*(who|which|that|where|when|WHOSE).*',
            'explanation': 'İlgi Cümlesi (Relative Clause)',
            'detailed': '"who", "which", "that" gibi ilgi zamirleri ile bağlanmış yan cümle. Bir ismi tanımlar veya açıklar.',
            'structure': 'İsim + İlgi Zamiri (who/which/that) + Yan Cümle',
            'examples': ['The man who called is my friend.', 'The book that I read was interesting.', 'The place where we met is closed.'],
            'tips': '"who" = kişiler için, "which" = nesneler için, "that" = hem kişi hem nesne için kullanılabilir. "where" = yer, "when" = zaman için.',
            'translation_tip': 'Türkçe\'de: "Arayan adam benim arkadaşım" gibi. İlgi zamiri Türkçe\'de genellikle "-en, -an" ekleriyle ifade edilir.'
        }
    }
    
    def __init__(self):
        """Initialize the grammar analyzer"""
        pass
    
    def analyze_sentence(self, sentence: str) -> Dict:
        """
        Analyze a sentence and return grammatical structure information
        
        Args:
            sentence: The sentence to analyze
            
        Returns:
            Dictionary containing analysis results
        """
        if not sentence or not sentence.strip():
            return {
                'success': False,
                'error': 'Boş cümle'
            }
        
        # Clean the sentence
        cleaned = self._clean_sentence(sentence)
        if not cleaned:
            return {
                'success': False,
                'error': 'Geçersiz cümle'
            }
        
        # Tokenize and tag
        tokens = word_tokenize(cleaned)
        if not tokens:
            return {
                'success': False,
                'error': 'Kelime bulunamadı'
            }
        
        pos_tags = pos_tag(tokens)
        
        # Analyze structure
        structure_info = self._analyze_structure(cleaned, pos_tags)
        
        # Analyze parts of speech
        pos_info = self._analyze_pos(pos_tags)
        
        # Identify sentence type
        sentence_type = self._identify_sentence_type(cleaned, pos_tags)
        
        # Find verb phrases
        verb_phrases = self._find_verb_phrases(pos_tags)
        
        # Find noun phrases
        noun_phrases = self._find_noun_phrases(pos_tags)
        
        # Find prepositional phrases
        prep_phrases = self._find_prepositional_phrases(pos_tags)
        
        # Grammar rules explanation
        grammar_rules = self._explain_grammar_rules(cleaned, pos_tags, structure_info)
        
        return {
            'success': True,
            'sentence': cleaned,
            'tokens': tokens,
            'pos_tags': [(word, tag, self.POS_EXPLANATIONS.get(tag, tag)) for word, tag in pos_tags],
            'sentence_type': sentence_type,
            'structure': structure_info,
            'parts_of_speech': pos_info,
            'verb_phrases': verb_phrases,
            'noun_phrases': noun_phrases,
            'prepositional_phrases': prep_phrases,
            'grammar_rules': grammar_rules
        }
    
    def _clean_sentence(self, sentence: str) -> str:
        """Clean and normalize sentence"""
        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', sentence.strip())
        # Remove leading/trailing punctuation except sentence-ending
        cleaned = re.sub(r'^[^\w\s]+', '', cleaned)
        # Ensure sentence ends with punctuation
        if cleaned and cleaned[-1] not in '.!?':
            cleaned += '.'
        return cleaned
    
    def _analyze_structure(self, sentence: str, pos_tags: List[Tuple[str, str]]) -> Dict:
        """Analyze sentence structure with detailed educational information"""
        # Convert POS tags to string pattern for matching
        pos_pattern = ' '.join([tag for _, tag in pos_tags])
        
        detected_structures = []
        structure_details = {}
        
        # Check each structure pattern
        for struct_name, struct_info in self.STRUCTURE_PATTERNS.items():
            pattern = struct_info['pattern']
            if re.search(pattern, pos_pattern, re.IGNORECASE):
                detected_structures.append(struct_name)
                structure_details[struct_name] = {
                    'name': struct_name,
                    'explanation': struct_info.get('explanation', ''),
                    'detailed': struct_info.get('detailed', ''),
                    'structure': struct_info.get('structure', ''),
                    'examples': struct_info.get('examples', []),
                    'tips': struct_info.get('tips', ''),
                    'translation_tip': struct_info.get('translation_tip', ''),
                    'pattern': pattern
                }
        
        # Determine main structure
        main_structure = 'simple'
        if 'complex' in detected_structures:
            main_structure = 'complex'
        elif 'compound' in detected_structures:
            main_structure = 'compound'
        elif detected_structures:
            main_structure = detected_structures[0]
        
        return {
            'main_structure': main_structure,
            'detected_structures': detected_structures,
            'details': structure_details
        }
    
    def _analyze_pos(self, pos_tags: List[Tuple[str, str]]) -> Dict:
        """Analyze parts of speech distribution"""
        pos_counts = defaultdict(int)
        pos_words = defaultdict(list)
        
        for word, tag in pos_tags:
            base_tag = tag[:2]  # Get base tag (e.g., 'NN' from 'NNS')
            pos_counts[base_tag] += 1
            pos_words[base_tag].append(word)
        
        return {
            'counts': dict(pos_counts),
            'words': {tag: words for tag, words in pos_words.items()},
            'explanations': {tag: self.POS_EXPLANATIONS.get(tag, tag) for tag in pos_counts.keys()}
        }
    
    def _identify_sentence_type(self, sentence: str, pos_tags: List[Tuple[str, str]]) -> Dict:
        """Identify the type of sentence"""
        sentence_lower = sentence.lower().strip()
        first_word = sentence_lower.split()[0] if sentence_lower.split() else ''
        first_tag = pos_tags[0][1] if pos_tags else ''
        
        # Check for question
        if sentence.strip().endswith('?'):
            return {
                'type': 'question',
                'explanation': 'Soru cümlesi: Cümle soru işareti ile bitiyor'
            }
        
        # Check for imperative
        if first_tag in ['VB', 'VBG'] and first_word not in ['i', 'you', 'we', 'they', 'he', 'she', 'it']:
            return {
                'type': 'imperative',
                'explanation': 'Emir cümlesi: Özne olmadan fiil ile başlıyor'
            }
        
        # Check for exclamation
        if sentence.strip().endswith('!'):
            return {
                'type': 'exclamatory',
                'explanation': 'Ünlem cümlesi: Cümle ünlem işareti ile bitiyor'
            }
        
        # Default declarative
        return {
            'type': 'declarative',
            'explanation': 'Bildirme cümlesi: Bilgi veren veya durum bildiren cümle'
        }
    
    def _find_verb_phrases(self, pos_tags: List[Tuple[str, str]]) -> List[Dict]:
        """Find verb phrases in the sentence"""
        verb_phrases = []
        current_vp = []
        
        for i, (word, tag) in enumerate(pos_tags):
            if tag.startswith('VB'):
                if current_vp:
                    verb_phrases.append({
                        'words': [w for w, _ in current_vp],
                        'tags': [t for _, t in current_vp],
                        'explanation': self._explain_verb_phrase(current_vp)
                    })
                    current_vp = []
                current_vp.append((word, tag))
            elif tag in ['MD', 'TO', 'RP'] and current_vp:
                current_vp.append((word, tag))
            elif current_vp:
                verb_phrases.append({
                    'words': [w for w, _ in current_vp],
                    'tags': [t for _, t in current_vp],
                    'explanation': self._explain_verb_phrase(current_vp)
                })
                current_vp = []
        
        if current_vp:
            verb_phrases.append({
                'words': [w for w, _ in current_vp],
                'tags': [t for _, t in current_vp],
                'explanation': self._explain_verb_phrase(current_vp)
            })
        
        return verb_phrases
    
    def _explain_verb_phrase(self, vp_tags: List[Tuple[str, str]]) -> str:
        """Explain a verb phrase"""
        tags = [tag for _, tag in vp_tags]
        words = [word for word, _ in vp_tags]
        
        if 'MD' in tags:
            modal = words[tags.index('MD')]
            return f'Yardımcı fiil "{modal}" ile başlayan fiil grubu'
        
        if 'TO' in tags:
            return 'Mastar (to + fiil) yapısı'
        
        if any(tag.startswith('VBG') for tag in tags):
            return 'Şimdiki zaman (-ing) yapısı'
        
        if any(tag.startswith('VBN') for tag in tags):
            return 'Geçmiş zaman ortacı yapısı'
        
        if any(tag.startswith('VBD') for tag in tags):
            return 'Geçmiş zaman fiil yapısı'
        
        if any(tag.startswith('VBZ') for tag in tags):
            return 'Geniş zaman, 3. tekil şahıs fiil yapısı'
        
        return 'Fiil grubu'
    
    def _find_noun_phrases(self, pos_tags: List[Tuple[str, str]]) -> List[Dict]:
        """Find noun phrases in the sentence"""
        noun_phrases = []
        current_np = []
        
        for i, (word, tag) in enumerate(pos_tags):
            if tag.startswith('NN') or tag in ['PRP', 'PRP$', 'DT']:
                current_np.append((word, tag))
            elif tag in ['JJ', 'CD'] and current_np:
                current_np.append((word, tag))
            elif current_np:
                noun_phrases.append({
                    'words': [w for w, _ in current_np],
                    'tags': [t for _, t in current_np],
                    'explanation': self._explain_noun_phrase(current_np)
                })
                current_np = []
        
        if current_np:
            noun_phrases.append({
                'words': [w for w, _ in current_np],
                'tags': [t for _, t in current_np],
                'explanation': self._explain_noun_phrase(current_np)
            })
        
        return noun_phrases
    
    def _explain_noun_phrase(self, np_tags: List[Tuple[str, str]]) -> str:
        """Explain a noun phrase"""
        tags = [tag for _, tag in np_tags]
        words = [word for word, _ in np_tags]
        
        if 'PRP' in tags:
            return 'Kişi zamiri'
        
        if 'PRP$' in tags:
            return 'İyelik zamiri'
        
        if 'DT' in tags and any(tag.startswith('NN') for tag in tags):
            determiner = words[tags.index('DT')]
            return f'İsim grubu: "{determiner}" belirteci ile başlayan'
        
        if any(tag.startswith('NN') for tag in tags):
            return 'İsim grubu'
        
        return 'İsim öbeği'
    
    def _find_prepositional_phrases(self, pos_tags: List[Tuple[str, str]]) -> List[Dict]:
        """Find prepositional phrases"""
        prep_phrases = []
        current_pp = []
        in_pp = False
        
        for word, tag in pos_tags:
            if tag == 'IN':
                if current_pp:
                    prep_phrases.append({
                        'words': [w for w, _ in current_pp],
                        'explanation': f'Edat grubu: "{current_pp[0][0]}" ile başlayan'
                    })
                current_pp = [(word, tag)]
                in_pp = True
            elif in_pp:
                current_pp.append((word, tag))
                if tag.startswith('NN') or tag in ['PRP', 'DT']:
                    in_pp = False
            elif current_pp and not in_pp:
                prep_phrases.append({
                    'words': [w for w, _ in current_pp],
                    'explanation': f'Edat grubu: "{current_pp[0][0]}" ile başlayan'
                })
                current_pp = []
        
        if current_pp:
            prep_phrases.append({
                'words': [w for w, _ in current_pp],
                'explanation': f'Edat grubu: "{current_pp[0][0]}" ile başlayan'
            })
        
        return prep_phrases
    
    def _explain_grammar_rules(self, sentence: str, pos_tags: List[Tuple[str, str]], structure_info: Dict) -> List[str]:
        """Explain grammar rules applied in the sentence"""
        rules = []
        
        # Subject-verb agreement
        subjects = [word for word, tag in pos_tags if tag in ['NN', 'NNS', 'PRP', 'NNP', 'NNPS']]
        verbs = [word for word, tag in pos_tags if tag.startswith('VB')]
        
        if subjects and verbs:
            first_subject = subjects[0]
            first_verb = verbs[0]
            first_subject_tag = next(tag for word, tag in pos_tags if word == first_subject)
            first_verb_tag = next(tag for word, tag in pos_tags if word == first_verb)
            
            if first_subject_tag in ['NN', 'NNP', 'PRP'] and first_verb_tag in ['VBZ', 'VBD']:
                rules.append(f'Özne-fiil uyumu: "{first_subject}" (tekil) ile "{first_verb}" (tekil fiil) uyumlu')
            elif first_subject_tag in ['NNS', 'NNPS'] and first_verb_tag in ['VBP', 'VBD']:
                rules.append(f'Özne-fiil uyumu: "{first_subject}" (çoğul) ile "{first_verb}" (çoğul fiil) uyumlu')
        
        # Article usage
        articles = [(word, tag) for word, tag in pos_tags if tag == 'DT']
        if articles:
            article_words = [word for word, _ in articles]
            if 'the' in article_words:
                rules.append('"the" belirteci: Belirli bir şeyi işaret eder')
            if 'a' in article_words or 'an' in article_words:
                rules.append('"a/an" belirteci: Belirsiz, genel bir şeyi işaret eder')
        
        # Tense identification
        verb_tags = [tag for _, tag in pos_tags if tag.startswith('VB')]
        if 'VBD' in verb_tags:
            rules.append('Geçmiş zaman: Cümle geçmiş zamanda')
        elif 'VBG' in verb_tags:
            rules.append('Şimdiki zaman: Cümle şimdiki zamanda (-ing)')
        elif 'VBZ' in verb_tags or 'VBP' in verb_tags:
            rules.append('Geniş zaman: Cümle geniş zamanda')
        
        # Structure explanation
        main_struct = structure_info.get('main_structure', 'simple')
        if main_struct in structure_info.get('details', {}):
            struct_detail = structure_info['details'][main_struct]
            rules.append(f'Cümle yapısı: {struct_detail["explanation"]}')
        
        return rules
