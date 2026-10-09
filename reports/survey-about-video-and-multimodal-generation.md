# Survey on Video and Multimodal Generation

## TL;DR
- Video and multimodal generation has evolved from GANs to advanced techniques like diffusion models and transformers that enhance realism and detail [1]. 
- Key contributions focus on improving spatiotemporal consistency in generated videos, addressing challenges of realism and dynamic sequences [2]. 
- Innovative architectures that integrate various modalities (e.g., video and audio) now dominate the landscape, offering enhanced control and efficiency [3]. 
- Comprehensive evaluation metrics are being developed to assess the quality and effectiveness of generated video content, emphasizing human perception [4][5]. 

## Background
Video and multimodal generation encompasses the use of algorithms to create video content from various inputs, such as text or images. The importance of this field lies in its applications across media, entertainment, education, and interaction. Key foundational works have traced the evolution of video generation technologies, demonstrating progress through multiple paradigms and highlighting the importance of understanding physical dynamics in video synthesis [1][6]. 

## Theoretical Foundations
The theoretical underpinnings of video generation have expanded significantly, with research illuminating the capabilities of world models that predict environmental dynamics beyond just pixel data [7]. This has led to sophisticated modeling techniques that can create more realistic video sequences and better synthesize the nuances of real-world interactions [2]. Integrating such models addresses fundamental challenges, such as maintaining continuity and coherence in generated content. 

## Model Architectures
Contemporary models in video generation utilize dual-branch architectures that distinguish between different physical dynamics [8]. This includes frameworks aimed at real-time multimodal video generation that reduce latency while enhancing interaction quality [3]. Innovative solutions have been put forth, such as unified approaches for joint video and audio generation, which allow for synchronized audiovisual content and improved interaction between modalities [3][4]. 

## Training Paradigms
Training methods are critical in optimizing video generation models. Recent advancements concentrate on high-efficiency pipelines for model training, employing multi-stage training strategies that enhance performance without excessive resource consumption [5]. Techniques like Parametric Trajectory Distillation demonstrate promising routes for reducing generation steps while preserving detail and training efficiency [8]. 

## Evaluation Metrics
As the capabilities of video generation models expand, so too have the frameworks for their evaluation. Emerging evaluation metrics focus not just on traditional measures of quality (e.g., FID, PSNR) but also on newer definitions of temporal coherence and human perception alignment [4][6]. Benchmark suites are now being developed to provide comprehensive performance assessments across multiple dimensions of video quality, underscoring the need for an evolved evaluation approach that better reflects user experience [5][6]. 

## Trends and Open Problems
Recent developments indicate a shift towards more unified architectures that seamlessly integrate various input modalities, enhancing coherence in video generation [4]. However, challenges remain, particularly in terms of parameter efficiency and addressing complex interactions across diverse content types. Future research directions will likely focus on improving generalizability and temporal consistency within generated content while exploring innovative multimodal frameworks.

## References
[1] Evolution of Video Generative Foundations. arxiv. https://arxiv.org/html/2604.06339v1 (2026-04-07)
[2] A Survey: Spatiotemporal Consistency in Video Generation. web. https://dl.acm.org/doi/10.1145/3802588 (2026-05-18)
[3] LiveTalk: Real-Time Multimodal Interactive Video Diffusion via Improved On-Policy Distillation. hf-search. https://huggingface.co/papers/2512.23576 (2025-12-29)
[4] Phase-aware video generation for physics-grounded dynamics and interactions. arxiv. https://arxiv.org/abs/2610.11791 (2026-10-08)
[5] MUG-V 10B: High-efficiency Training Pipeline for Large Video Generation Models. hf-search. https://huggingface.co/papers/2510.17519 (2025-10-20)
[6] LoomVideo: Unifying Multimodal Inputs into Video Generation and Editing. web. https://arxiv.org/abs/2606.06042 (2026-06-04)
[7] Video Generation Models as World Models: Efficient Paradigms, Architectures and Algorithms. arxiv. https://arxiv.org/html/2603.28489v3 (2026-07-04)
[8] JoVA: Unified Multimodal Learning for Joint Video-Audio Generation. hf-search. https://huggingface.co/papers/2512.13677 (2025-12-15)
