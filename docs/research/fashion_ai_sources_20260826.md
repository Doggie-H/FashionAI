# Fashion AI sources retained for roadmap

## Dataset and benchmark candidates

1. **DeepFashion2 Dataset** — https://github.com/switchablenorms/deepfashion2
   - Search result describes a comprehensive fashion dataset with diverse images across 13 popular clothing categories.
   - Potential use: perception/landmark/detection/segmentation experimentation only after checking the dataset license, annotations, privacy and commercial-use terms.

2. **Fashionpedia** — https://fashionpedia.github.io/home/
   - Search result describes fine-grained fashion segmentation and a fashion ontology.
   - Potential use: vocabulary/ontology alignment and segmentation evaluation; not direct authority for personalized outfit advice.

3. **DeepFashion database (CUHK MMLab)** — https://mmlab.ie.cuhk.edu.hk/projects/DeepFashion.html
   - Search result describes a large fashion image database spanning shop and consumer images with attributes.
   - Potential use: visual retrieval/perception research, subject to license and representative-data review.

4. **Computational Technologies for Fashion Recommendation** — https://dl.acm.org/doi/full/10.1145/3627100
   - Search result notes the lack of a satisfactory benchmark for every subtask in personalized fashion recommendation.
   - Implication: do not claim an "expert" stylist from one public dataset; use task-specific, human-reviewed evaluation slices.

5. **FashionFail** — https://arxiv.org/html/2404.08582v1
   - Search result identifies a robustness benchmark for fashion object detection/segmentation failure cases.
   - Potential use: negative/robustness slice for visual ingestion quality gates.

## Governing implications

- Public visual datasets may help perception, taxonomy mapping, retrieval, segmentation or robustness. They do not directly authorize a production system to infer fit, body suitability, culture-sensitive appropriateness, or fashion-expert judgment.
- A production fashion intelligence program requires user-consented wardrobe data, versioned style/occasion/constraint labels, reviewer rubrics, train/validation/test separation, privacy/retention policy, bias analysis, online feedback monitoring and rollback.
- Verify original data terms and commercial licensing before downloading, training, fine-tuning, or mixing any dataset into a product corpus.
