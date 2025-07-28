# task_manager/ai/services2.py
import json
from django.conf import settings
from .client import get_ai_client
from .constants import DEFAULT_MODEL, DEFAULT_MODEL_1, DEFAULT_MODEL_4, DEFAULT_MODEL_10, DEFAULT_MODEL_11


class ProjectProposalService:
    def __init__(self):
        self.client = get_ai_client()

    def generate_project_proposal(self, team_data, project_requirements=None):
        """
        Generate a project proposal based on team member skills and optional requirements
        
        Args:
            team_data (dict): Team information including members and their skills
            project_requirements (str, optional): Additional project requirements
            
        Returns:
            dict: Generated project proposal in JSON format
        """
        try:
            # Prepare the prompt for AI
            prompt = self._build_prompt(team_data, project_requirements)
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=DEFAULT_MODEL_11,  
                messages=[
                    {
                        "role": "system",
                        "content": "You are a project management AI assistant. Generate detailed project proposals with task distribution based on team member skills. Always respond with valid JSON format."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            # Parse the AI response
            ai_response = response.choices[0].message.content.strip()
            
            # Try to extract JSON from the response
            project_proposal = self._parse_ai_response(ai_response)
            
            return {
                'success': True,
                'proposal': project_proposal
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to generate project proposal: {str(e)}"
            }

    def _build_prompt(self, team_data, project_requirements):
        """Build the prompt for AI based on team data and requirements"""
        
        # Format team member information
        members_info = []
        for member in team_data['members']:
            member_info = f"""
            - User ID: {member['user_id']}
            - Email: {member['email']}
            - Skills: {', '.join(member['all_skills']) if member['all_skills'] else 'No skills listed'}
            - Experience: {member['full_experience'] if member['full_experience'] else 'No experience provided'}
            """
            members_info.append(member_info)
        
        prompt = f"""
Based on the following team information, generate a comprehensive project proposal:

Team: {team_data['team_name']} (ID: {team_data['team_id']})

Team Members:
{''.join(members_info)}

Additional Requirements: {project_requirements if project_requirements else 'None specified'}

Please generate a project proposal in the following JSON format:
{{
    "project_name": "Suggested project name",
    "description": "Detailed project description",
    "estimated_duration": "Duration in weeks/months",
    "phases": [
        {{
            "phase_name": "Phase name",
            "description": "Phase description",
            "duration": "Duration",
            "tasks": [
                {{
                    "task_name": "Task name",
                    "description": "Task description",
                    "assigned_to": "user_id",
                    "assigned_to_email": "user_email",
                    "estimated_hours": "number",
                    "priority": "Low/Medium/High",
                    "skills_required": ["list of skills needed"]
                }}
            ]
        }}
    ],
    "resource_requirements": [
        "List of resources needed"
    ],
    "risk_assessment": [
        {{
            "risk": "Risk description",
            "mitigation": "Mitigation strategy"
        }}
    ],
    "success_metrics": [
        "List of success criteria"
    ]
}}

Make sure to:
1. Assign tasks based on team members' skills and experience
2. Create a balanced workload distribution
3. Suggest realistic timelines
4. Include all team members in appropriate roles
5. Return only valid JSON format
"""
        return prompt

    def _parse_ai_response(self, ai_response):
        """Parse AI response and extract JSON"""
        try:
            # Try to find JSON in the response
            start_idx = ai_response.find('{')
            end_idx = ai_response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = ai_response[start_idx:end_idx]
                return json.loads(json_str)
            else:
                # If no JSON found, return the raw response
                return {"raw_response": ai_response}
                
        except json.JSONDecodeError:
            # If JSON parsing fails, return the raw response
            return {"raw_response": ai_response}

    def validate_proposal(self, proposal, team_data):
        """
        Validate the generated proposal against team data
        
        Args:
            proposal (dict): Generated project proposal
            team_data (dict): Original team data
            
        Returns:
            dict: Validation results
        """
        validation_results = {
            'valid': True,
            'warnings': [],
            'errors': []
        }
        
        try:
            # Get list of valid user IDs
            valid_user_ids = [str(member['user_id']) for member in team_data['members']]
            
            # Check if proposal has required structure
            if 'phases' not in proposal:
                validation_results['errors'].append("Missing 'phases' in proposal")
                validation_results['valid'] = False
                return validation_results
            
            # Validate task assignments
            for phase in proposal.get('phases', []):
                for task in phase.get('tasks', []):
                    assigned_to = str(task.get('assigned_to', ''))
                    if assigned_to and assigned_to not in valid_user_ids:
                        validation_results['warnings'].append(
                            f"Task '{task.get('task_name')}' assigned to non-team member: {assigned_to}"
                        )
            
            # Check workload distribution
            task_counts = {}
            for phase in proposal.get('phases', []):
                for task in phase.get('tasks', []):
                    assigned_to = str(task.get('assigned_to', ''))
                    if assigned_to in valid_user_ids:
                        task_counts[assigned_to] = task_counts.get(assigned_to, 0) + 1
            
            # Warn about uneven distribution
            if task_counts:
                avg_tasks = sum(task_counts.values()) / len(task_counts)
                for user_id, count in task_counts.items():
                    if count > avg_tasks * 1.5:
                        validation_results['warnings'].append(
                            f"User {user_id} has significantly more tasks than average"
                        )
            
        except Exception as e:
            validation_results['errors'].append(f"Validation error: {str(e)}")
            validation_results['valid'] = False
        
        return validation_results