# %% [markdown] 
# # Stress-testing our results
# At this point, we've shown a lot of cool results, but qualitative data
# is fickle and subject to both selection effects and confirmation bias.

# %%
%load_ext autoreload
%autoreload 2

# %%
try:
    import algebraic_value_editing
except ImportError:
    commit = "eb1b349"  # Stable commit
    get_ipython().run_line_magic(  # type: ignore
        magic_name="pip",
        line=(
            "install -U"
            f" git+https://github.com/montemac/algebraic_value_editing.git@{commit}"
        ),
    )


# %%
import torch
import pandas as pd 
from typing import List, Callable, Dict 
from jaxtyping import Float

from transformer_lens.HookedTransformer import HookedTransformer

from algebraic_value_editing import hook_utils, prompt_utils, completion_utils
from algebraic_value_editing.prompt_utils import RichPrompt

# %%
model_name = "gpt2-xl"

device: str = "cuda:3" if torch.cuda.is_available() else "cpu"
model: HookedTransformer = HookedTransformer.from_pretrained(
    model_name, device="cpu"
)
_ = model.to(device)
_ = torch.set_grad_enabled(False)
torch.manual_seed(0) # For reproducibility

# %% [markdown]
# ## Measuring the magnitudes of the steering vectors at each residual stream position
# How "big" are our edits, compared to the normal activations? Let's first
# examine what the residual stream magnitudes tend to be, by taking the L2
# norm of the residual stream at each sequence position. We'll do this for
# a range of prompts at a range of locations in the forward pass.
# 
# (Most of the below prompts were generated by GPT4.)

# %%
prompt_magnitudes: List[Float[torch.Tensor, "position"]] = []
prompts: List[str] = [
    "Bush did 9/11 because",
    "Barack Obama was born in",
    "Shrek starts off in a swamp",
    "I went up to my friend and said",
    "I talk about weddings constantly",
    "I bring up weddings in every situation",
    (
        "I hate talking about weddings. Instead, let's talk about a totally"
        " different topic, like the impact of NGDP on the price of gold."
    ),
    "Artificial intelligence is transforming industries and reshaping the way we live, work, and interact.",
    "Climate change is one of the most pressing issues of our time, and we must take immediate action to reduce our carbon footprint.",
    "The rise of electric vehicles has led to an increased demand for lithium-ion batteries, driving innovation in the field of battery technology.",
    "The blockchain technology has the potential to revolutionize industries such as finance, supply chain management, and digital identity verification.",
    "CRISPR-Cas9 is a groundbreaking gene editing technology that allows scientists to make precise changes to an organism's DNA.",
    "Quantum computing promises to solve problems that are currently intractable for classical computers, opening up new frontiers in fields like cryptography and materials science.",
    "Virtual reality and augmented reality are transforming the way we experience and interact with digital content.",
    "3D printing is revolutionizing manufacturing, enabling the creation of complex and customized products on demand.",
    "The Internet of Things (IoT) is connecting everyday objects to the internet, providing valuable data and insights for businesses and consumers.",
    "Machine learning algorithms are becoming increasingly sophisticated, enabling computers to learn from data and make predictions with unprecedented accuracy.",
    "Renewable energy sources like solar and wind power are essential for reducing greenhouse gas emissions and combating climate change.",
    "The development of autonomous vehicles has the potential to greatly improve safety and efficiency on our roads.",
    "The human microbiome is a complex ecosystem of microbes living in and on our bodies, and its study is shedding new light on human health and disease.",
    "The use of drones for delivery, surveillance, and agriculture is rapidly expanding, with many companies investing in drone technology.",
    "The sharing economy, powered by platforms like Uber and Airbnb, is disrupting traditional industries and changing the way people access goods and services.",
    "Deep learning is a subset of machine learning that uses neural networks to model complex patterns in data.",
    "The discovery of exoplanets has fueled the search for extraterrestrial life and advanced our understanding of planetary systems beyond our own.",
    "Nanotechnology is enabling the development of new materials and devices at the atomic and molecular scale.",
    "The rise of big data is transforming industries, as companies seek to harness the power of data analytics to gain insights and make better decisions.",
    "Advancements in robotics are leading to the development of robots that can perform complex tasks and interact with humans in natural ways.",
    "The gig economy is changing the nature of work, as more people turn to freelancing and contract work for flexibility and autonomy.",
    "The Mars rover missions have provided valuable data on the geology and climate of the Red Planet, paving the way for future manned missions.",
    "The development of 5G networks promises faster and more reliable wireless connectivity, enabling new applications in areas like IoT and smart cities.",
    "Gene therapy offers the potential to treat genetic diseases by replacing, modifying, or regulating specific genes.",
    "The use of facial recognition technology raises important questions about privacy, surveillance, and civil liberties.",
    "Precision agriculture uses data and technology to optimize crop yields and reduce environmental impacts.",
    "Neuromorphic computing aims to develop hardware that mimics the structure and function of the human brain.",
    "Breaking news: Local man wins the lottery and plans to donate half of his earnings to charity",
    "How to grow your own organic vegetables in your backyard – step by step guide",
    "omg I can't believe this new phone has such a terrible battery life, it doesn't even last a full day!",
    "Top 10 travel destinations you must visit before you die",
    "What are the best ways to invest in cryptocurrency?",
    "I've been using this acne cream for a month and it's only making my skin worse, anyone else having this issue?",
    "The secret to a happy and healthy relationship is communication and trust",
    "Rumor has it that the famous celebrity couple is getting a divorce",
    "I recently switched to a vegan diet and I feel so much better, I can't believe I didn't do it sooner",
    "Can someone help me with my math homework? I'm stuck on this problem...",
    "UFO sightings have increased in the past few years, are we close to making contact with extraterrestrial life?",
    "The government is hiding the truth about climate change and how it's affecting our planet",
    "Are video games causing violence among teenagers? A new study says yes",
    "A new study reveals the benefits of drinking coffee every day",
    "lol this new meme is hilarious, I can't stop laughing!",
    "I'm so tired of people arguing about politics on the internet, can't we all just get along?",
    "I love this new TV show, the characters are so well-developed and the plot is amazing",
    "A devastating earthquake hit the city last night, leaving thousands homeless",
    "Scientists discover a new species of fish deep in the ocean",
    "Why are people still believing in flat earth theory?",
    "The local animal shelter is holding an adoption event this weekend, don't miss it!",
    "The city is planning to build a new park in the neighborhood, residents are excited",
    "My dog ate my homework, literally, can anyone relate?",
    "This new diet trend is taking the world by storm, but is it really effective?",
] 
DF_COLS: List[str] = ["Prompt", "Activation Location", "Activation Name", "Magnitude"]
sampling_kwargs: Dict[str, float] = {
    "temperature": 1.0,
    "top_p": 0.3,
    "freq_penalty": 1.0
}

# %% [markdown]
# ## Plotting the distribution of residual stream magnitudes
# As the forward pass progresses through the network, the residual
# stream tends to increase in magnitude in an exponential fashion. This
# is easily visible in the histogram below, which shows the distribution
# of residual stream magnitudes for each layer of the network. The activation
# distribution translates by an almost constant factor each 6 layers,
# and the x-axis (magnitude) is log-scale, so magnitude apparently
# increases exponentially with layer number.*
#
# (Intriguingly, there are a few outlier residual streams which have
# magnitude over an order of magnitude larger than the rest.)
# 
# Alex's first guess for the exponential magnitude increase was: Each OV circuit is a linear function of the
# residual stream given a fixed attention pattern. Then you add the head
# OV outputs back into a residual stream, which naively doubles the
# magnitude assuming the OV outputs have similar norm to the input
# residual stream. The huge problem with this explanation is layernorm,
# which is applied to the inputs to the attention and MLP layers. This
# should basically whiten the input to the OV circuits if the gain
# parameters are close to 1. 
# 
# * Stefan Heimersheim previously noticed this phenomenon in GPT2-small.
# %%
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

def magnitude_histogram(df: pd.DataFrame) -> go.Figure:
    """Plot a histogram of the residual stream magnitudes for each layer
    of the network."""
    assert "Magnitude" in df.columns, "Dataframe must have a 'Magnitude' column"

    df["LogMagnitude"] = np.log10(df["Magnitude"])
    fig = px.histogram(df, x="LogMagnitude", color="Activation Location",  
              marginal="rug", histnorm="percent", nbins=100, opacity=0.5, barmode="overlay", color_discrete_sequence=px.colors.sequential.Rainbow[::-1])

    fig.update_layout(legend_title_text="Layer Number",
                      title="Residual Stream Magnitude Distribution by Layer Number",
                      xaxis_title="Magnitude (log 10)",
                      yaxis_title="Percentage of streams")

    return fig
# %%
activation_locations_6: List[int] = torch.arange(0, 48, 6).tolist()

# %%
# Create an empty dataframe with the required columns
prompt_df = pd.DataFrame(
    columns=DF_COLS
)

from algebraic_value_editing import prompt_utils

# Loop through activation locations and prompts
for act_loc in activation_locations_6:
    act_name: str = prompt_utils.get_block_name(block_num=act_loc)
    for prompt in prompts:
        mags: torch.Tensor = hook_utils.prompt_magnitudes(
            model=model, prompt=prompt, act_name=act_name
        ).cpu() 

        # Create a new dataframe row with the current data
        row = pd.DataFrame(
            {
                "Prompt": prompt,
                "Activation Location": act_loc,
                "Activation Name": act_name,
                "Magnitude": mags,
            }
        )

        # Append the new row to the dataframe
        prompt_df = pd.concat([prompt_df, row], ignore_index=True)
# %%
fig: go.Figure = magnitude_histogram(prompt_df)
fig.show() 

# %% [markdown]
# The fast magnitude gain
# occurs in the first 7 layers. Let's find out where.

# %% 
activation_locations: List[int] = list(range(7))
first_6_df = pd.DataFrame(columns=DF_COLS)

for act_loc in activation_locations:
    act_name: str = prompt_utils.get_block_name(block_num=act_loc)
    for prompt in prompts:
        mags: torch.Tensor = hook_utils.prompt_magnitudes(
            model=model, prompt=prompt, act_name=act_name
        ).cpu() 

        # Create a new dataframe row with the current data
        row = pd.DataFrame(
            {
                "Prompt": prompt,
                "Activation Location": act_loc,
                "Activation Name": act_name,
                "Magnitude": mags,
            }
        )

        # Append the new row to the dataframe
        first_6_df = pd.concat([first_6_df, row], ignore_index=True)

fig: go.Figure = magnitude_histogram(first_6_df)
fig.show()

# %% [markdown]
# Most of the jump happens after the 0th layer in the transformer, and
# a smaller jump happens between the 1st and 2nd layers.

# %% [markdown]
# ## Plotting steering vector magnitudes against layer number
# Let's see whether the steering vector magnitudes also increase
# exponentially with layer number. It turns out that the answer is yes,
# although the zeroth position (the `<|endoftext|>` token) has a much larger
# magnitude than the rest. (This possibly explains the outlier
# magnitudes for the prompt histograms.)

# %%
# Create an empty dataframe with the required columns
all_resid_pre_locations: List[int] = torch.arange(0, 48, 1).tolist()
addition_df = pd.DataFrame(
    columns=DF_COLS
)

from algebraic_value_editing import prompt_utils

# Loop through activation locations and prompts
for act_loc in all_resid_pre_locations:
    anger_calm_additions: List[RichPrompt] = [
        RichPrompt(prompt="Anger", coeff=1, act_name=act_loc), 
        RichPrompt(prompt="Calm", coeff=-1, act_name=act_loc)
    ]
    act_name: str = prompt_utils.get_block_name(block_num=act_loc)
    for addition in anger_calm_additions:
        mags: torch.Tensor = hook_utils.prompt_magnitudes(
            model=model, prompt=addition.prompt, act_name=act_name
        ).cpu()

        for pos, mag in enumerate(mags):
            # Create a new dataframe row with the current data
            row = pd.DataFrame(
                {
                    "Prompt": [f"{addition.prompt}, pos {pos}"],
                    "Activation Location": [act_loc],
                    "Activation Name": [act_name],
                    "Magnitude": [mag],
                }
            )

            # Append the new row to the dataframe
            addition_df = pd.concat([addition_df, row], ignore_index=True)

# %% Make a plotly line plot of the RichPrompt magnitudes

def line_plot(df: pd.DataFrame, log_y: bool = True, title: str = "ActivationAddition Prompt Magnitude by Layer Number", legend_title_text: str = "Prompt") -> go.Figure:
    """ Make a line plot of the RichPrompt magnitudes. """
    for col in ["Prompt", "Activation Location", "Magnitude"]:
        assert col in df.columns, f"Column {col} not in dataframe"

    if log_y:
        df["LogMagnitude"] = np.log10(df["Magnitude"])

    fig = px.line(df, x="Activation Location", y="LogMagnitude" if log_y else "Magnitude", color="Prompt", color_discrete_sequence=px.colors.sequential.Rainbow[::-1])

    fig.update_layout(legend_title_text=legend_title_text,
                        title=title,  
                        xaxis_title="Layer Number",
                        yaxis_title=f"Magnitude{' (log 10)' if log_y else ''}")

    return fig

# %% 
fig: go.Figure = line_plot(addition_df)
fig.show()

# %% [markdown] Now let's plot how the steering vector magnitudes change with layer
# number. These magnitudes are the L2 norms of the net activation
# vectors (adding one residual stream for "Anger" and subtracting the
# residual streams for "Calm"). Let's sanity-check that the magnitudes
# look reasonable, given what we just learned about the usual distribution of
# residual stream magnitudes.

def steering_magnitudes_dataframe(model: HookedTransformer, act_adds: List[RichPrompt], locations: List[int]) -> pd.DataFrame:
    """ Compute the relative magnitudes of the steering vectors at the
    locations in the model. """
    steering_df = pd.DataFrame(
        columns=DF_COLS
    )

    for act_loc in locations:
        relocated_adds: List[RichPrompt] = [
            RichPrompt(prompt=act_add.prompt, coeff=act_add.coeff, act_name=act_loc) for act_add in act_adds
        ]
        mags: torch.Tensor = hook_utils.steering_vec_magnitudes(
            model=model, act_adds=relocated_adds
        ).cpu()

        prompt1_toks, prompt2_toks = [model.to_str_tokens(addition.prompt) for addition in relocated_adds]

        for pos, mag in enumerate(mags):    
            tok1, tok2 = prompt1_toks[pos], prompt2_toks[pos]    
            row = pd.DataFrame(
                {
                    "Prompt": [f"{tok1}-{tok2}, pos {pos}"],
                    "Activation Location": [act_loc],
                    "Magnitude": [mag],
                }
            )

            # Append the new row to the dataframe
            steering_df = pd.concat([steering_df, row], ignore_index=True)

    return steering_df

# %% Make a plotly line plot of the steering vector magnitudes
anger_calm_additions: List[RichPrompt] = [
    RichPrompt(prompt="Anger", coeff=1, act_name=0),
    RichPrompt(prompt="Calm", coeff=-1, act_name=0)
]
steering_df: pd.DataFrame = steering_magnitudes_dataframe(model=model, act_adds=anger_calm_additions, locations=all_resid_pre_locations)

fig: go.Figure = line_plot(steering_df)
fig.show()
# %% [markdown]
# These steering vector magnitudes 

# %% Let's plot the steering vector magnitudes against the prompt
# magnitudes
def relative_magnitudes_dataframe(model: HookedTransformer, act_adds: List[RichPrompt], prompt: str, locations: List[int]) -> pd.DataFrame:
    """ Compute the relative magnitudes of the steering vectors at the
    locations in the model. """
    relative_df = pd.DataFrame(
        columns=DF_COLS
    )

    for act_loc in locations:
        relocated_adds: List[RichPrompt] = [
            RichPrompt(prompt=act_add.prompt, coeff=act_add.coeff, act_name=act_loc) for act_add in act_adds
        ]
        mags: torch.Tensor = hook_utils.steering_magnitudes_relative_to_prompt(
            model=model, prompt=prompt, act_adds=relocated_adds
        ).cpu()

        prompt1_toks, prompt2_toks = [model.to_str_tokens(addition.prompt) for addition in relocated_adds]

        for pos, mag in enumerate(mags):    
            tok1, tok2 = prompt1_toks[pos], prompt2_toks[pos]    
            row = pd.DataFrame(
                {
                    "Prompt": [f"{tok1}-{tok2}, pos {pos}"],
                    "Activation Location": [act_loc],
                    "Magnitude": [mag],
                }
            )

            # Append the new row to the dataframe
            relative_df = pd.concat([relative_df, row], ignore_index=True)

    return relative_df

# %% Make a line plot of the relative steering vector magnitudes 
anger_calm_additions: List[RichPrompt] = [
    RichPrompt(prompt="Anger", coeff=1, act_name=0),
    RichPrompt(prompt="Calm", coeff=-1, act_name=0)
] 
relative_df: pd.DataFrame = relative_magnitudes_dataframe(model=model, act_adds=anger_calm_additions, prompt="I think you're", locations=all_resid_pre_locations)

fig: go.Figure = line_plot(relative_df, log_y=False, legend_title_text="Residual stream", title="Positionwise Steering Vector Magnitude / Prompt Magnitude")

# Add a subtitle
fig.update_layout(
    annotations=[
        go.layout.Annotation(
            text="Prompt: \"I think you're\"",
            showarrow=False,
            xref="paper",
            yref="paper",
            x=0.06,
            y=1.015,  
            xanchor="center",
            yanchor="bottom",
            font=dict(size=13)
        )
    ]
)
fig.show()

# %% [markdown]
# We don't know why the relative magnitude decreases during the forward
# pass. 
# 
# (The `<|endoftext|>` - `<|endoftext|>` magnitude is always 0,
# because
# it's the zero vector. Thus, its relative magnitude is also 0.)

# %% [markdown] 
# Great, so there are reasonable relative magnitudes of the `Anger` -
# `Calm` steering vector.
# Is this true for other vectors? Some vectors, like ` anger` - ` calm`,
# have little qualitative impact. Maybe they're low-norm?

# %%
anger_calm_additions: List[RichPrompt] = [
    RichPrompt(prompt=" anger", coeff=1, act_name=0),
    RichPrompt(prompt=" calm", coeff=-1, act_name=0)
]
relative_df: pd.DataFrame = relative_magnitudes_dataframe(model=model, act_adds=anger_calm_additions, prompt="I think you're", locations=all_resid_pre_locations)

fig: go.Figure = line_plot(relative_df, log_y=False, legend_title_text="Residual stream", title="Positionwise Steering Vector Magnitude / Prompt Magnitude")

# Add a subtitle
fig.update_layout(
    annotations=[
        go.layout.Annotation(
            text="Prompt: \"I think you're\"",
            showarrow=False,
            xref="paper",
            yref="paper",
            x=0.06,
            y=1.015,  
            xanchor="center",
            yanchor="bottom",
            font=dict(size=13)
        )
    ]
)
fig.show()

# %% [markdown]
# Nope, that's not the explanation. 

# %% [markdown]
# ## Injecting similar-magnitude random vectors
# Let's try injecting random vectors with similar magnitudes to the
# steering vectors. If GPT2XL is mostly robust to this addition, this
# suggests the presence of lots of tolerance to noise, and seems like
# _very slight_ evidence of superposition (since a bunch of
# not-quite-orthogonal features will noisily unembed, and the model has
# to be performant in the face of this). 
# 
# But mostly, it just seems like a
# good additional data point to have. 

# %%
# Get the steering vector magnitudes for the anger-calm steering vector
# at layer 6
anger_calm_additions: List[RichPrompt] = [
    RichPrompt(prompt="Anger", coeff=10, act_name=20),
    RichPrompt(prompt="Calm", coeff=-10, act_name=20)
]
num_anger_completions: int = 5
anger_vec: Float[torch.Tensor, "batch seq d_model"] = hook_utils.get_prompt_activations(model, anger_calm_additions[0]) + hook_utils.get_prompt_activations(model, anger_calm_additions[1])
# %%
# For reference, here are the effects of this steering vector on two
# prompts. (You'll have to scroll to see both tables.)
anger_prompts: List[str] = [
    "I think you're",
    "Shrek starts off with a scene about",
]
for prompt in anger_prompts:
    print(completion_utils.bold_text(f"Prompt: {prompt}"))
    completion_utils.print_n_comparisons(model=model,
        prompt=prompt,
        tokens_to_generate=90,
        rich_prompts=anger_calm_additions,
        num_comparisons=num_anger_completions,
        seed=1, # Seed 0 has some disturbing outputs for the modified vector! (What you might expect if you +Anger and -Calm)
        **sampling_kwargs
    )

# %%
mags: torch.Tensor = hook_utils.steering_vec_magnitudes(
    model=model, act_adds=anger_calm_additions
).cpu()

# Make normally drawn random vector with about the same magnitude as the steering
# vector (dmodel is 1600 for GPT2XL)
rand_act: Float[torch.Tensor, "seq d_model"] = torch.randn(size=[len(mags), 1600])

# Rescale appropriately
scaling_factors: torch.Tensor = mags / rand_act.norm(dim=1)
rand_act = rand_act * scaling_factors[:, None]
rand_act[0,:] = 0 # Zero out the first token

print(f"Steering vector magnitudes: {mags}\nRandom vector magnitudes: {rand_act.norm(dim=1)}\n")

# Compare maximum magnitude of steering vector to maximum magnitude of
# random vector
print(f"Max steering vector value: {anger_vec.max():.1f}")
print(f"Max random vector value: {rand_act.max():.1f}")
rand_act = rand_act.unsqueeze(0) # Add a batch dimension

# %% 
# Get the model device so we can move rand_act off of the cpu 
model_device: torch.device = next(model.parameters()).device
# Get the hook function
hook: Callable = hook_utils.hook_fn_from_activations(activations=rand_act.to(model_device))
act_name: str = prompt_utils.get_block_name(block_num=20) 
hooks: Dict[str, Callable] = {act_name: hook}

for prompt in anger_prompts:
    rand_df = completion_utils.gen_using_hooks(model=model, prompt_batch=[prompt] * num_anger_completions, hook_fns=hooks, tokens_to_generate=60, seed=1, **sampling_kwargs)
    completion_utils.pretty_print_completions(rand_df)

# %% [markdown]
# The random vector injection has little effect on the output, given
# similar magnitudes. We tentatively infer that GPT-2-XL is not easy to
# break/modify via generic random intervention,
# and is instead controllable through consistent feature directions
# which are added to its forward pass by steering vectors. 
# %% [markdown]
# # Testing the hypothesis that we're "basically injecting extra tokens"
# There's a hypothesis that the steering vectors are just injecting
# extra tokens into the forward pass. In some situations, this makes
# sense. Given prompt "I love you because", if we inject a `_wedding` token at position 1 with large
# coefficient, perhaps the model just "sees" the sentence "_wedding love
# you because". 
# 
# However, in general, it's not clear what this hypothesis means. Tokens
# are a discrete quantity. You can't have more than one in a single
# position. You can't have three times `_wedding` and then negative
# three times `_` (space), on top of `I`. That's just not a thing which
# can be done using "just tokens." 
# 
# Even though this hypothesis isn't strictly true, there are still
# interesting versions to investigate. For example, consider the
# steering vector formed by adding `Anger` and subtracting `Calm` at
# layer 20, with coefficient 10. Perhaps what we're really doing is 

# %%