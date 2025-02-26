from log_processor.user.users import Users
import pandas as pd
from collections import Counter


class EventSequenceAnalysis:
    def __init__(self, users: Users):
        self.users = users
    
    def generate_report(self):
        sequences = []

        for user in self.users.users:
            print(f"Processing user {user.username}")
            sequence = user.get_event_sequence()
            sequences.extend([x[1] for x in sequence])
        
        subsequences = []
        for length in range(1, 6):
            for i in range(len(sequences) - length + 1):
                subsequences.append(tuple(sequences[i:i + length]))

        subsequence_counts = Counter(subsequences)
        df = pd.DataFrame(subsequence_counts.items(), columns=['Subsequence', 'Frequency'])
        df = df.sort_values(by='Frequency', ascending=False)
        df.to_csv('output/subsequence_frequencies.csv', index=False)