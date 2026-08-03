from datetime import datetime, timedelta
from bson import ObjectId
from database.db import get_predictions_collection

class PredictionRecord:
    def __init__(self, doc: dict):
        self.id = str(doc.get('_id'))
        self.userId = str(doc.get('userId'))
        self.filename = doc.get('filename', 'Unknown')
        self.prediction = doc.get('prediction', 'Unknown')
        self.purity = doc.get('purity', 'Unknown')
        self.confidence = doc.get('confidence', '0%')
        self.probabilities = doc.get('probabilities', {})
        self.reason = doc.get('reason', '')
        self.predictionTime = doc.get('predictionTime', '')
        self.status = doc.get('status', 'completed')
        self.createdAt = doc.get('createdAt')
        
        # Reliability classification assessment
        self.reliability = self._calculate_reliability()

    def _calculate_reliability(self) -> str:
        """Calculates reliability score rating based on model confidence."""
        try:
            conf_num = float(str(self.confidence).replace('%', '').strip())
            if conf_num >= 90.0:
                return "HIGH RELIABILITY"
            elif conf_num >= 75.0:
                return "MODERATE RELIABILITY"
            else:
                return "LOW RELIABILITY"
        except Exception:
            return "STANDARD ASSESS"

    @classmethod
    def get_by_id(cls, prediction_id: str):
        try:
            doc = get_predictions_collection().find_one({'_id': ObjectId(prediction_id)})
            return cls(doc) if doc else None
        except Exception:
            return None

    @classmethod
    def create_record(cls, user_id: str, filename: str, result: dict, status: str = "completed"):
        now = datetime.utcnow()
        doc = {
            'userId': user_id,
            'filename': filename,
            'prediction': result.get('class', 'Unknown'),
            'purity': result.get('purity', 'Unknown'),
            'confidence': result.get('confidence', '0%'),
            'probabilities': result.get('probabilities', {}),
            'reason': result.get('reason', ''),
            'predictionTime': result.get('prediction_time', ''),
            'status': status,
            'createdAt': now
        }
        
        preds_col = get_predictions_collection()
        res = preds_col.insert_one(doc)
        doc['_id'] = res.inserted_id
        return cls(doc)

    @classmethod
    def get_user_history(cls, user_id: str, limit: int = 20):
        try:
            preds_col = get_predictions_collection()
            cursor = preds_col.find({'userId': str(user_id)}).sort('createdAt', -1).limit(limit)
            return [cls(doc) for doc in cursor]
        except Exception as e:
            print(f"Error fetching user prediction history: {e}")
            return []

    @classmethod
    def get_analytics_summary(cls, user_id: str):
        """
        Calculates analytics breakdown counters (Total, Male, Female, Hybrid, Unknown)
        and monthly usage distribution.
        """
        try:
            preds_col = get_predictions_collection()
            records = list(preds_col.find({'userId': str(user_id)}))
            
            total_tests = len(records)
            male_count = 0
            female_count = 0
            hybrid_count = 0
            unknown_count = 0
            
            for r in records:
                pred = str(r.get('prediction', '')).lower()
                purity = str(r.get('purity', '')).lower()
                
                if pred == 'unknown' or 'unknown' in purity:
                    unknown_count += 1
                elif 'male' in pred:
                    male_count += 1
                elif 'female' in pred:
                    female_count += 1
                elif 'hybrid' in pred or purity.startswith('pure'):
                    hybrid_count += 1
                else:
                    hybrid_count += 1
            
            # Calculate monthly usage for last 6 months
            now = datetime.utcnow()
            monthly_data = []
            for i in range(5, -1, -1):
                m_date = now - timedelta(days=i*30)
                m_name = m_date.strftime('%b %Y')
                m_count = sum(
                    1 for r in records 
                    if r.get('createdAt') and r.get('createdAt').month == m_date.month and r.get('createdAt').year == m_date.year
                )
                monthly_data.append({'month': m_name, 'count': m_count})

            pure_ratio = (hybrid_count / total_tests * 100) if total_tests > 0 else 0.0

            return {
                'total_tests': total_tests,
                'male_count': male_count,
                'female_count': female_count,
                'hybrid_count': hybrid_count,
                'unknown_count': unknown_count,
                'pure_ratio': round(pure_ratio, 1),
                'monthly_usage': monthly_data
            }
        except Exception as e:
            print(f"Error computing analytics summary: {e}")
            return {
                'total_tests': 0,
                'male_count': 0,
                'female_count': 0,
                'hybrid_count': 0,
                'unknown_count': 0,
                'pure_ratio': 0.0,
                'monthly_usage': []
            }

    @classmethod
    def search_and_filter(cls, user_id: str, search_query: str = "", class_filter: str = "all"):
        """
        Filters user predictions based on search term and class category.
        """
        try:
            preds_col = get_predictions_collection()
            query = {'userId': str(user_id)}
            
            if search_query and search_query.strip():
                regex_pattern = {'$regex': search_query.strip(), '$options': 'i'}
                query['$or'] = [
                    {'filename': regex_pattern},
                    {'prediction': regex_pattern},
                    {'purity': regex_pattern}
                ]
                
            if class_filter and class_filter != 'all':
                cf = class_filter.lower()
                if cf == 'hybrid':
                    query['$or'] = [{'prediction': {'$regex': 'hybrid', '$options': 'i'}}, {'purity': {'$regex': '^pure', '$options': 'i'}}]
                elif cf == 'male':
                    query['prediction'] = {'$regex': 'male', '$options': 'i'}
                elif cf == 'female':
                    query['prediction'] = {'$regex': 'female', '$options': 'i'}
                elif cf == 'unknown':
                    query['$or'] = [{'prediction': 'UNKNOWN'}, {'purity': {'$regex': 'unknown', '$options': 'i'}}]

            cursor = preds_col.find(query).sort('createdAt', -1).limit(100)
            return [cls(doc) for doc in cursor]
        except Exception as e:
            print(f"Error in search_and_filter: {e}")
            return []
