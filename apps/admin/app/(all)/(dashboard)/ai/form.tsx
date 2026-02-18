/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { useForm } from "react-hook-form";
import { Lightbulb } from "lucide-react";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { IFormattedInstanceConfiguration, TInstanceAIConfigurationKeys } from "@plane/types";
// components
import type { TControllerInputFormField } from "@/components/common/controller-input";
import { ControllerInput } from "@/components/common/controller-input";
// hooks
import { useInstance } from "@/hooks/store";

type IInstanceAIForm = {
  config: IFormattedInstanceConfiguration;
};

type AIFormValues = Record<TInstanceAIConfigurationKeys, string>;

const PROVIDERS = [
  { value: "openai", label: "OpenAI", placeholder: "gpt-4o-mini", keyPlaceholder: "sk-..." },
  { value: "gemini", label: "Google Gemini", placeholder: "gemini-2.0-flash", keyPlaceholder: "AIza..." },
  { value: "deepseek", label: "DeepSeek", placeholder: "deepseek-chat", keyPlaceholder: "sk-..." },
] as const;

type ProviderValue = (typeof PROVIDERS)[number]["value"];

export function InstanceAIForm(props: IInstanceAIForm) {
  const { config } = props;
  // store
  const { updateInstanceConfigurations } = useInstance();
  // provider state (managed outside react-hook-form to avoid type issues)
  const [selectedProvider, setSelectedProvider] = useState<ProviderValue>("openai");
  const providerInfo = PROVIDERS.find((p) => p.value === selectedProvider) ?? PROVIDERS[0];
  // form data
  const {
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = useForm<AIFormValues>({
    defaultValues: {
      LLM_API_KEY: config["LLM_API_KEY"],
      LLM_MODEL: config["LLM_MODEL"],
    },
  });

  const modelField: TControllerInputFormField = {
    key: "LLM_MODEL",
    type: "text",
    label: "LLM Model",
    description: <>Model name for the selected provider.</>,
    placeholder: providerInfo.placeholder,
    error: Boolean(errors.LLM_MODEL),
    required: false,
  };

  const apiKeyField: TControllerInputFormField = {
    key: "LLM_API_KEY",
    type: "password",
    label: "API Key",
    description: <>Your API key from the provider&apos;s dashboard.</>,
    placeholder: providerInfo.keyPlaceholder,
    error: Boolean(errors.LLM_API_KEY),
    required: false,
  };

  const onSubmit = async (formData: AIFormValues) => {
    await updateInstanceConfigurations({
      ...formData,
      LLM_PROVIDER: selectedProvider,
    } as Record<string, string>)
      .then(() =>
        setToast({
          type: TOAST_TYPE.SUCCESS,
          title: "Success",
          message: "AI Settings updated successfully",
        })
      )
      .catch((err) => console.error(err));
  };

  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <div>
          <div className="pb-1 text-18 font-medium text-primary">AI Provider</div>
          <div className="text-13 font-regular text-tertiary">Configure your LLM provider and credentials.</div>
        </div>

        {/* Provider selector — not part of react-hook-form */}
        { }
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-secondary">Provider</span>
          <select
            value={selectedProvider}
            onChange={(e) => setSelectedProvider(e.target.value as ProviderValue)}
            className="w-full max-w-xs rounded-md border border-border-primary bg-primary px-3 py-2 text-sm text-primary focus:outline-none focus:ring-2 focus:ring-accent-primary"
          >
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </label>

        {/* Model + API key */}
        <div className="grid-col grid w-full grid-cols-1 items-center justify-between gap-x-12 gap-y-8 lg:grid-cols-3">
          {[modelField, apiKeyField].map((field) => (
            <ControllerInput
              key={field.key}
              control={control}
              type={field.type}
              name={field.key}
              label={field.label}
              description={field.description}
              placeholder={field.placeholder}
              error={field.error}
              required={field.required}
            />
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-4 items-start">
        <Button variant="primary" size="lg" onClick={() => void handleSubmit(onSubmit)()} loading={isSubmitting}>
          {isSubmitting ? "Saving" : "Save changes"}
        </Button>

        <div className="relative inline-flex items-center gap-1.5 rounded-sm border border-accent-subtle bg-accent-subtle px-4 py-2 text-caption-sm-regular text-accent-secondary">
          <Lightbulb className="size-4" />
          <div>
            If you have a preferred AI models vendor, please get in{" "}
            <a className="underline font-medium" href="https://plane.so/contact">
              touch with us.
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
