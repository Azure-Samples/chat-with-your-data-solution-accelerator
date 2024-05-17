# Changelog

## [1.2.0](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/compare/v1.1.0...v1.2.0) (2024-05-17)


### Features

* Generate and add image captions to search index when image is ingested.  ([#928](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/928)) ([b8e34aa](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/commit/b8e34aabd1effb41109e71822e59b1f2aa9ad220))
* Generate embeddings for images ([#892](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/892)) ([a96bde6](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/commit/a96bde6616e33d41a796cfb4a2c2e7705b8369ce))
* Remove LangChain from post prompt tool ([#937](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/937)) ([21064e7](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/commit/21064e7ca1215c395f3d14619b3a90abf75b96c7))
* Store image embeddings in search index ([#921](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/921)) ([f903af9](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/commit/f903af95536e59f4f3c47d7ffe1902d0df183ac4))


### Bug Fixes

* Add `max_tokens` to chat completions ([#934](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/934)) ([392d437](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/commit/392d43742e7302234236df95476cd2819a094d00))
* Error viewing images in Explore Data page ([#936](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/936)) ([0d12d63](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/commit/0d12d6340bb32ca58c220520470165c9f8009939))
* Fix computer vision for deployments ([#919](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/919)) ([548a767](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/commit/548a7670363a5e7ae369fe518ff2c64441138ee6))
* Fix generate_arm_templates.sh script, reformat all Bicep files ([#922](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/922)) ([8c46627](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/commit/8c46627299e7a13f802879c9dcde7ef2f4cf8262))
* handle BlobDelete event type in `batch_push_results` ([#893](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/893)) ([f27b68e](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/commit/f27b68effadfaf7cc1d79c1d852d306a806ad74e))
* Keep the Admin.py as uppercase naming to allow the streamlit pick it as is. ([#912](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/912)) ([4150955](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/commit/4150955afb7dbdaeffb9ab55e0dc0f4fdf24cfe1))
* Revert linting bug ([#932](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/932)) ([d4e417a](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/commit/d4e417ae5c98e3fe04b3dace75bd92182ecc199a))

## [1.1.0](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/compare/v1.0.0...v1.1.0) (2024-05-14)


### Features

* [IV] Reprocess All documents functionality  ([#870](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/870)) ([89e328b](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/commit/89e328b9aceb00cc3f92eb9179947239a931f909))

## 1.0.0 (2024-05-14)


### Features

* Implement hybrid search on BYOD endpoint. ([#891](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/891)) ([8309d54](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/commit/8309d546f036617ea4b244f446474f054c46fe6e))
* Use openai client for Azure BYOD ([#831](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/831)) ([fc62160](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/commit/fc621602c457f50c883e16ea7006f796f2171d70))


### Bug Fixes

* [IV] Appropriate messages on Explore & Delete page when index not created ([#849](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/849)) ([50b9900](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/commit/50b99001885b5886191b78a9117e6b34c6597f5d))
* lower function syntax ([95ddc43](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/commit/95ddc434eb82f0120d57663086bbb29ae90989a8))
* Removing index creation from init of AzureSearchHelper.py ([#872](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/872)) ([6b8f125](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/commit/6b8f12531b3190740bf2c9319898b7dcfcafc106))
* update local port to use 5050 ([#847](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/847)) ([e755928](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/commit/e755928cbbe43a77e63af1b665f72bb5faed6b7a))
