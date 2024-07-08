export class MyDataSource implements DataSource {
    public readonly name = "my-datasource";
    public async renderData(
      context: TurnContext,
      memory: Memory,
      tokenizer: Tokenizer,
      maxTokens: number
    ): Promise<RenderedPromptSection<string>> {
      const input = memory.getValue('temp.input') as string;
      let knowledge = "There's no knowledge found.";
  
      // hard-code knowledge
      if (input?.includes("shuttle bus")) {
        knowledge = "Company's shuttle bus may be 15 minutes late on rainy days.";
      } else if (input?.includes("cafe")) {
        knowledge = "The Cafe's available time is 9:00 to 17:00 on working days and 10:00 to 16:00 on weekends and holidays."
      }
  
      return {
        output: knowledge,
        length: knowledge.length,
        tooLong: false
      }
    }
  }