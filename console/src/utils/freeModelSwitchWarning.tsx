import { Checkbox, Modal } from "@agentscope-ai/design";

const FREE_MODEL_WARNING_DISABLED_KEY =
  "minions_free_model_switch_warning_disabled";

const PROVIDER_WEBSITE_SAMPLES: Record<string, string> = {};

interface FreeModelWarningProvider {
  id: string;
  base_url?: string;
}

interface FreeModelWarningModel {
  is_free?: boolean;
}

interface ConfirmFreeModelSwitchOptions {
  provider: FreeModelWarningProvider;
  model: FreeModelWarningModel;
}

function isWarningDisabled(): boolean {
  return localStorage.getItem(FREE_MODEL_WARNING_DISABLED_KEY) === "1";
}

function disableWarning(): void {
  localStorage.setItem(FREE_MODEL_WARNING_DISABLED_KEY, "1");
}

function getProviderWebsite(provider: FreeModelWarningProvider): string {
  return PROVIDER_WEBSITE_SAMPLES[provider.id] ?? provider.base_url ?? "#";
}

export async function confirmFreeModelSwitch({
  provider,
  model,
}: ConfirmFreeModelSwitchOptions): Promise<boolean> {
  if (!model.is_free || isWarningDisabled()) {
    return true;
  }

  const providerWebsite = getProviderWebsite(provider);
  let dontShowAgain = false;

  return new Promise<boolean>((resolve) => {
    let settled = false;

    const settle = (value: boolean) => {
      if (settled) return;
      settled = true;
      resolve(value);
    };

    Modal.confirm({
      title: "免费模型提示",
      content: (
        <div>
          <div>免费模型可能存在服务不稳定的情况，详情请参考提供商服务条款：</div>
          <div className="minions-free-model-warning-link-row">
            <a href={providerWebsite} target="_blank" rel="noreferrer">
              {providerWebsite}
            </a>
          </div>
          <div className="minions-free-model-warning-checkbox-row">
            <Checkbox
              onChange={(event) => {
                dontShowAgain = Boolean(event?.target?.checked);
              }}
            >
              今后不再提示
            </Checkbox>
          </div>
        </div>
      ),
      okText: "确认",
      cancelText: "取消",
      onOk: () => {
        if (dontShowAgain) {
          disableWarning();
        }
        settle(true);
      },
      onCancel: () => settle(false),
      afterClose: () => settle(false),
    });
  });
}
