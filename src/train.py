from gymnasium.wrappers import TimeLimit
from env_hiv import HIVPatient

env = TimeLimit(
    env=HIVPatient(domain_randomization=False), max_episode_steps=200
)  # The time wrapper limits the number of steps in an episode at 200.
# Now is the floor is yours to implement the agent and train it.
state_dim = env.observation_space.shape[0]
n_action = env.action_space.n
# You have to implement your own agent.
# Don't modify the methods names and signatures, but you can add methods.
# ENJOY!

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions import Categorical

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions import Categorical

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class policyNetwork(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(state_dim, 128, dtype = torch.float64)
        self.fc2 = nn.Linear(128, n_action, dtype = torch.float64)

    def forward(self, x):
        if x.dim() == 1:
            x = x.unsqueeze(dim=0)
        x = F.relu(self.fc1(x))
        action_scores = self.fc2(x)
        return F.softmax(action_scores,dim=1)

    def sample_action(self, x):
        probabilities = self.forward(x)
        action_distribution = Categorical(probabilities)
        return action_distribution.sample().item()

    def log_prob(self, x, a):
        probabilities = self.forward(x)
        action_distribution = Categorical(probabilities)
        return action_distribution.log_prob(a)
    
from tqdm import trange
import numpy as np

class valueNetwork(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(state_dim, 128, dtype = torch.float64)
        self.fc2 = nn.Linear(128, 1, dtype = torch.float64)

    def forward(self, x):
        if x.dim() == 1:
            x = x.unsqueeze(dim=0)
        x = F.relu(self.fc1(x))
        return self.fc2(x)
    
class a2c_agent:
    def __init__(self, config, policy_network, value_network):
        self.device = "cuda" if next(policy_network.parameters()).is_cuda else "cpu"
        self.scalar_dtype = next(policy_network.parameters()).dtype
        self.policy = policy_network
        self.value = value_network
        self.gamma = config['gamma'] if 'gamma' in config.keys() else 0.99
        lr = config['learning_rate'] if 'learning_rate' in config.keys() else 0.001
        self.optimizer = torch.optim.Adam(list(self.policy.parameters()) + list(self.value.parameters()),lr=lr)
        self.nb_episodes = config['nb_episodes'] if 'nb_episodes' in config.keys() else 1
        self.entropy_coefficient = config['entropy_coefficient'] if 'entropy_coefficient' in config.keys() else 0.001

    def sample_action(self, x):
        probabilities = self.policy(torch.as_tensor(x))
        action_distribution = Categorical(probabilities)
        action = action_distribution.sample()
        log_prob = action_distribution.log_prob(action)
        entropy = action_distribution.entropy()
        return action.item(), log_prob, entropy
    
    def one_gradient_step(self, env):
        # run trajectories until done
        episodes_sum_of_rewards = []
        log_probs = []
        returns = []
        values = []
        entropies = []
        for ep in range(self.nb_episodes):
            x,_ = env.reset()
            rewards = []
            episode_cum_reward = 0
            while(True):
                a, log_prob, entropy = self.sample_action(x)
                y,r,d,_,_ = env.step(a)
                values.append(self.value(torch.as_tensor(x)).squeeze(dim=0))
                log_probs.append(log_prob)
                entropies.append(entropy)
                rewards.append(r)
                episode_cum_reward += r
                x=y
                if d:
                    # compute returns-to-go
                    new_returns = []
                    G_t = self.value(torch.as_tensor(x)).squeeze(dim=0)
                    for r in reversed(rewards):
                        G_t = r + self.gamma * G_t
                        new_returns.append(G_t)
                    new_returns = list(reversed(new_returns))
                    returns.extend(new_returns)
                    episodes_sum_of_rewards.append(episode_cum_reward)
                    break
        # make loss        
        returns = torch.cat(returns)
        values = torch.cat(values)
        log_probs = torch.cat(log_probs)
        entropies = torch.cat(entropies)
        advantages = returns - values
        pg_loss = -(advantages.detach() * log_probs).mean()
        entropy_loss = -entropies.mean()
        critic_loss = advantages.pow(2).mean()
        loss = pg_loss + critic_loss + self.entropy_coefficient * entropy_loss
        # gradient step
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        return np.mean(episodes_sum_of_rewards)

    def train(self, env, nb_rollouts):
        avg_sum_rewards = []
        for ep in trange(nb_rollouts):
            avg_sum_rewards.append(self.one_gradient_step(env))
        return avg_sum_rewards


    
class ProjectAgent:

    def __init__(self):
        config = {'gamma':0.99,
          'learning_rate':0.01,
          'nb_episodes':10,
          'entropy_coefficient': 1e-3}
        policy_network = policyNetwork()
        value_network = valueNetwork()
        self.device = "cuda" if next(policy_network.parameters()).is_cuda else "cpu"
        self.scalar_dtype = next(policy_network.parameters()).dtype
        self.policy = policy_network
        self.value = value_network
        self.gamma = config['gamma'] if 'gamma' in config.keys() else 0.99
        lr = config['learning_rate'] if 'learning_rate' in config.keys() else 0.001
        self.optimizer = torch.optim.Adam(list(self.policy.parameters()) + list(self.value.parameters()),lr=lr)
        self.nb_episodes = config['nb_episodes'] if 'nb_episodes' in config.keys() else 1
        self.entropy_coefficient = config['entropy_coefficient'] if 'entropy_coefficient' in config.keys() else 0.001

    def sample_action(self, x):
        probabilities = self.policy(torch.as_tensor(x))
        action_distribution = Categorical(probabilities)
        action = action_distribution.sample()
        log_prob = action_distribution.log_prob(action)
        entropy = action_distribution.entropy()
        return action.item(), log_prob, entropy
    
    def one_gradient_step(self, env):
        # run trajectories until done
        episodes_sum_of_rewards = []
        log_probs = []
        returns = []
        values = []
        entropies = []
        for ep in range(self.nb_episodes):
            x,_ = env.reset()
            rewards = []
            episode_cum_reward = 0
            while(True):
                a, log_prob, entropy = self.sample_action(x)
                y,r,d,_,_ = env.step(a)
                values.append(self.value(torch.as_tensor(x)).squeeze(dim=0))
                log_probs.append(log_prob)
                entropies.append(entropy)
                rewards.append(r)
                episode_cum_reward += r
                x=y
                if d:
                    # compute returns-to-go
                    new_returns = []
                    G_t = self.value(torch.as_tensor(x)).squeeze(dim=0)
                    for r in reversed(rewards):
                        G_t = r + self.gamma * G_t
                        new_returns.append(G_t)
                    new_returns = list(reversed(new_returns))
                    returns.extend(new_returns)
                    episodes_sum_of_rewards.append(episode_cum_reward)
                    break
        # make loss        
        returns = torch.cat(returns)
        values = torch.cat(values)
        log_probs = torch.cat(log_probs)
        entropies = torch.cat(entropies)
        advantages = returns - values
        pg_loss = -(advantages.detach() * log_probs).mean()
        entropy_loss = -entropies.mean()
        critic_loss = advantages.pow(2).mean()
        loss = pg_loss + critic_loss + self.entropy_coefficient * entropy_loss
        # gradient step
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        return np.mean(episodes_sum_of_rewards)

    def train(self, env, nb_rollouts):
        avg_sum_rewards = []
        for ep in trange(nb_rollouts):
            avg_sum_rewards.append(self.one_gradient_step(env))
        return avg_sum_rewards
    
    def act(self, observation, use_random=False):
        x,_,_ = self.sample_action(observation)
        return x

    def save(self, path):
        torch.save(self.policy.state_dict(), path + '/policy_weights.pth')
        torch.save(self.value.state_dict(),  path +'/value_weights.pth')
        pass

    def load(self):
        pi = policyNetwork()  # Instantiate the model with the same architecture
        pi.load_state_dict(torch.load('policy_weights.pth', map_location=torch.device('cpu')))
        self.policy = pi 
        V = policyNetwork()  # Instantiate the model with the same architecture
        pi.load_state_dict(torch.load('policy_weights.pth',  map_location=torch.device('cpu')))
        self.policy = pi 
        pass


config = {'gamma':0.99,
          'learning_rate':0.01,
          'nb_episodes':10,
          'entropy_coefficient': 1e-3}

# pi = policyNetwork(env).to(device)
# V  = valueNetwork(env).to(device)
# # agent = a2c_agent(config, pi, V)
# agent = ProjectAgent(config,pi,V)
# agent.load()

# from evaluate import evaluate_HIV, evaluate_HIV_population
# # Keep the following lines to evaluate your agent unchanged.
# score_agent: float = evaluate_HIV(agent=agent, nb_episode=1)
# score_agent_dr: float = evaluate_HIV_population(agent=agent, nb_episode=15)
# with open(file="score.txt", mode="w") as f:
#     f.write(f"{score_agent}\n{score_agent_dr}")